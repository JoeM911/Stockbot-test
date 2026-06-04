"""
Autonomous trader: scans every 60s and decides direction, style, and sizing.
In AUTO mode it runs both daily and intraday scanners simultaneously — when
both timeframes agree the conviction is boosted and the trade is labelled
'DAY'; daily-only signals become 'SWING'. The user only needs to set aggression.
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Dict

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None


def _now_et():
    if _ET:
        return datetime.now(_ET)
    from datetime import timedelta
    return datetime.now(timezone(timedelta(hours=-4)))


class AutoTrader:
    def __init__(self, alpaca_client, scanner, sentiment=None):
        self.alpaca    = alpaca_client
        self.scanner   = scanner
        self.sentiment = sentiment
        self.enabled   = True
        self.mode      = "both"       # "long", "short", "both"
        self.trade_style = "auto"     # "auto", "swing", "day"
        self.aggression    = 5
        self.max_positions = 5
        self.risk_pct      = 0.05
        self.max_trade_usd = 10_000
        self.stop_pct      = 0.03
        self.target_pct    = 0.06
        self.portfolio_target: float | None = None
        self._position_styles: Dict[str, str] = {}   # sym → "swing" | "day"
        self.activity: List[dict] = []

    # ------------------------------------------------------------------ public

    @staticmethod
    def session_type() -> str:
        now = _now_et()
        if now.weekday() >= 5:
            return "closed"
        mins = now.hour * 60 + now.minute
        if 4 * 60 <= mins < 9 * 60 + 30:  return "pre_market"
        if 9 * 60 + 30 <= mins < 16 * 60: return "regular"
        if 16 * 60 <= mins < 20 * 60:     return "after_hours"
        return "closed"

    def set_aggression(self, level: int):
        self.aggression    = level
        t = (level - 1) / 9.0
        self.risk_pct      = round(0.02 + t * 0.13, 3)
        self.stop_pct      = round(0.02 + t * 0.04, 3)
        self.target_pct    = round(0.04 + t * 0.10, 3)
        self.max_positions = max(2, round(3 + t * 7))
        self.max_trade_usd = round(5_000 + t * 45_000)

    def set_mode(self, mode: str):
        self.mode = mode if mode in ("long", "short", "both") else "both"

    def set_trade_style(self, style: str):
        self.trade_style = style if style in ("auto", "swing", "day") else "auto"

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def get_status(self) -> dict:
        return {
            "enabled":          self.enabled,
            "mode":             self.mode,
            "trade_style":      self.trade_style,
            "aggression":       self.aggression,
            "max_positions":    self.max_positions,
            "risk_pct":         self.risk_pct,
            "stop_pct":         self.stop_pct,
            "target_pct":       self.target_pct,
            "max_trade_usd":    self.max_trade_usd,
            "portfolio_target": self.portfolio_target,
            "activity":         self.activity[:30],
        }

    # ---------------------------------------------------------------- scanning

    async def _build_signal_map(self, universe: List[str], session: str) -> Dict[str, dict]:
        """
        AUTO mode: run daily + intraday scanners in parallel.
        When both timeframes agree on direction the conviction is bumped +1
        and the style is set to 'day'. Conflicting signals are dropped.
        Daily-only → 'swing'. Intraday-only → 'day'.
        """
        fetch_intraday = session == "regular"

        if fetch_intraday:
            daily_sigs, intra_sigs = await asyncio.gather(
                self.scanner.scan(universe),
                self.scanner.scan_intraday(universe),
            )
        else:
            daily_sigs = await self.scanner.scan(universe)
            intra_sigs = []

        daily_map = {s["symbol"]: s for s in daily_sigs}
        intra_map = {s["symbol"]: s for s in intra_sigs}

        combined: Dict[str, dict] = {}

        all_syms = set(daily_map) | set(intra_map)
        for sym in all_syms:
            d = daily_map.get(sym)
            i = intra_map.get(sym)

            if d and i:
                if d["action"] == i["action"] and d["action"] in ("BUY", "SHORT"):
                    # Both timeframes agree → confirmed, higher conviction, day style
                    merged_signals = i["signals"] + [f"Confirmed {d['action']} 1D"]
                    conviction = min(3, max(d["conviction"], i["conviction"]) + 1)
                    combined[sym] = {**i, "signals": merged_signals,
                                     "conviction": conviction, "style": "day",
                                     "reason": "Multi-TF confirmed"}
                elif d["action"] in ("BUY", "SHORT") and d["conviction"] >= i["conviction"]:
                    combined[sym] = {**d, "style": "swing"}
                elif i["action"] in ("BUY", "SHORT"):
                    combined[sym] = {**i, "style": "day"}
                # else: conflicting direction — skip
            elif d and d["action"] in ("BUY", "SHORT"):
                combined[sym] = {**d, "style": "swing"}
            elif i and i["action"] in ("BUY", "SHORT"):
                combined[sym] = {**i, "style": "day"}

        return combined

    # ----------------------------------------------------------------- run loop

    async def run(self, universe: List[str], manager) -> None:
        if not self.enabled:
            return
        session = self.session_type()
        if session == "closed":
            return

        # Forced day mode: regular hours only
        if self.trade_style == "day" and session != "regular":
            return

        extended = (self.trade_style == "swing") and session in ("pre_market", "after_hours")

        try:
            account      = await self.alpaca.get_account()
            positions    = await self.alpaca.get_positions()
            buying_power = float(account["buying_power"])
            equity       = float(account.get("equity") or account.get("portfolio_value") or 0)

            longs  = {p["symbol"]: p for p in positions if float(p["qty"]) > 0}
            shorts = {p["symbol"]: p for p in positions if float(p["qty"]) < 0}
            held   = {p["symbol"]: p for p in positions}

            # ---- Day-trade flat: close day-style positions before 3:45pm ----
            if session == "regular" and held:
                now_et = _now_et()
                if now_et.hour * 60 + now_et.minute >= 15 * 60 + 45:
                    day_positions = {
                        sym: pos for sym, pos in held.items()
                        if self._position_styles.get(sym) == "day"
                        or self.trade_style == "day"
                    }
                    for sym, pos in list(day_positions.items()):
                        qty = float(pos["qty"])
                        if qty > 0:
                            await self._close_long(sym, qty, "Day trade — flat before close", manager)
                        else:
                            await self._cover_short(sym, qty, "Day trade — flat before close", manager)
                        held.pop(sym, None)
                        self._position_styles.pop(sym, None)
                    if self.trade_style == "day":
                        return

            # ---- EXIT longs: stop-loss or take-profit -----------------------
            for sym, pos in list(longs.items()):
                if sym not in held: continue
                entry   = float(pos["avg_entry_price"])
                current = float(pos["current_price"])
                if entry <= 0: continue
                pnl_pct = (current - entry) / entry
                if pnl_pct <= -self.stop_pct:
                    await self._close_long(sym, pos["qty"], f"Stop loss {pnl_pct*100:.1f}%", manager)
                    held.pop(sym, None)
                    self._position_styles.pop(sym, None)
                elif pnl_pct >= self.target_pct:
                    await self._close_long(sym, pos["qty"], f"Take profit +{pnl_pct*100:.1f}%", manager)
                    held.pop(sym, None)
                    self._position_styles.pop(sym, None)

            # ---- EXIT shorts: stop-loss or take-profit ----------------------
            for sym, pos in list(shorts.items()):
                if sym not in held: continue
                entry   = float(pos["avg_entry_price"])
                current = float(pos["current_price"])
                if entry <= 0: continue
                pnl_pct = (entry - current) / entry
                if pnl_pct <= -self.stop_pct:
                    await self._cover_short(sym, pos["qty"], f"Short stop loss {pnl_pct*100:.1f}%", manager)
                    held.pop(sym, None)
                    self._position_styles.pop(sym, None)
                elif pnl_pct >= self.target_pct:
                    await self._cover_short(sym, pos["qty"], f"Short take profit +{pnl_pct*100:.1f}%", manager)
                    held.pop(sym, None)
                    self._position_styles.pop(sym, None)

            # ---- Portfolio target -------------------------------------------
            if self.portfolio_target and equity >= self.portfolio_target:
                return
            if len(held) >= self.max_positions:
                return

            # ---- Build signal candidates ------------------------------------
            if self.trade_style == "auto":
                sig_map = await self._build_signal_map(universe, session)
                signals = list(sig_map.values())
            elif self.trade_style == "day":
                raw = await self.scanner.scan_intraday(universe)
                signals = [{**s, "style": "day"} for s in raw]
            else:
                raw = await self.scanner.scan(universe)
                signals = [{**s, "style": "swing"} for s in raw]

            long_candidates  = [s for s in signals if s["action"] == "BUY"   and s["symbol"] not in held]
            short_candidates = [s for s in signals if s["action"] == "SHORT" and s["symbol"] not in held]

            # In AUTO style the bot picks direction itself; mode override only applies in SWING/DAY
            if self.trade_style != "auto":
                if self.mode == "long":  short_candidates = []
                if self.mode == "short": long_candidates  = []

            if not long_candidates and not short_candidates:
                return

            # ---- Sentiment boost (skip for pure intraday) ------------------
            sent_map: dict = {}
            use_sentiment = self.sentiment and (
                self.trade_style in ("auto", "swing") or
                any(s.get("style") == "swing" for s in long_candidates + short_candidates)
            )
            if use_sentiment:
                try:
                    all_cands = long_candidates + short_candidates
                    syms = [c["symbol"] for c in all_cands[:10]]
                    sent_scores = await self.sentiment.scan_sentiment(syms)
                    sent_map = {s["symbol"]: s["score"] for s in sent_scores}
                except Exception:
                    pass

            def score(sig, direction):
                tech   = abs(sig.get("change_pct", 0)) + sig.get("conviction", 1) * 2
                # Multi-TF confirmed gets a bonus
                if sig.get("reason") == "Multi-TF confirmed":
                    tech += 3
                s_score = sent_map.get(sig["symbol"], 0)
                social  = s_score if direction == "long" else -s_score
                return tech + social * 2

            long_candidates.sort( key=lambda s: score(s, "long"),  reverse=True)
            short_candidates.sort(key=lambda s: score(s, "short"), reverse=True)

            best_long  = long_candidates[0]  if long_candidates  else None
            best_short = short_candidates[0] if short_candidates else None

            # Sentiment veto
            if best_long  and sent_map.get(best_long["symbol"],  0) < -0.3: best_long  = None
            if best_short and sent_map.get(best_short["symbol"], 0) >  0.3: best_short = None

            pick = None
            if best_long and best_short:
                pick = best_long if score(best_long, "long") >= score(best_short, "short") else best_short
            elif best_long:
                pick = best_long
            elif best_short:
                pick = best_short

            if not pick:
                return

            sym        = pick["symbol"]
            price      = pick["price"]
            action     = pick["action"]
            conviction = pick.get("conviction", 1)
            style      = pick.get("style", "swing")
            if price <= 0:
                return

            # ---- Build human-readable reasons --------------------------------
            reasons = list(pick["signals"])
            if pick.get("reason") == "Multi-TF confirmed":
                reasons.append("Multi-TF confirmed")
            s_score = sent_map.get(sym)
            if s_score is not None:
                pct = round(abs(s_score) * 100)
                reasons.append(f"{'Bullish' if s_score > 0 else 'Bearish'} sentiment {pct}%")
            reasons.append(f"Style: {style.upper()}")
            reasons.append(f"Conviction {conviction}/3")
            if extended:
                reasons.append("Pre-market" if session == "pre_market" else "After-hours")

            # ---- Position sizing --------------------------------------------
            conviction_scale = {1: 1.0, 2: 1.5, 3: 2.0}.get(conviction, 1.0)
            target_scale = 1.0
            if self.portfolio_target and equity > 0 and equity / self.portfolio_target >= 0.90:
                target_scale = 0.5
            risk      = self.risk_pct * (0.5 if extended else 1.0) * target_scale * conviction_scale
            trade_usd = min(buying_power * risk, self.max_trade_usd * conviction_scale)
            qty       = max(1, int(trade_usd / price))

            self._position_styles[sym] = style

            if action == "BUY":
                await self._open_long(sym, qty, price, reasons, style, manager, extended=extended)
            else:
                await self._open_short(sym, qty, price, reasons, style, manager, extended=extended)

        except Exception as e:
            print(f"[AutoTrader] {e}")

    # ----------------------------------------------------------------- private

    def _log(self, entry: dict):
        self.activity.insert(0, entry)
        self.activity = self.activity[:100]

    async def _open_long(self, symbol, qty, price, reasons, style, manager, extended=False):
        try:
            if extended:
                limit  = round(price * 1.002, 2)
                result = await self.alpaca.place_order(symbol, qty, "buy", "limit", limit_price=limit, extended_hours=True)
            else:
                result = await self.alpaca.place_order(symbol, qty, "buy", "market")
            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "BUY", "symbol": symbol,
                "qty": qty, "price": round(price, 2),
                "reasons": reasons, "style": style,
                "order_id": result.get("id"), "extended": extended,
            }
            self._log(entry)
            await manager.broadcast({"type": "bot_activity", "data": entry})
            print(f"[AutoTrader] BUY {qty} {symbol} @ ${price:.2f} [{style}] — {reasons}")
        except Exception as e:
            print(f"[AutoTrader] open_long {symbol}: {e}")

    async def _close_long(self, symbol, qty, reason, manager):
        try:
            session  = self.session_type()
            extended = session in ("pre_market", "after_hours")
            if extended:
                result = await self.alpaca.place_order(symbol, abs(float(qty)), "sell", "limit",
                                                       limit_price=None, extended_hours=True, use_current_price=True)
            else:
                result = await self.alpaca.place_order(symbol, abs(float(qty)), "sell", "market")
            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "SELL", "symbol": symbol,
                "qty": abs(float(qty)), "reason": reason, "order_id": result.get("id"),
            }
            self._log(entry)
            await manager.broadcast({"type": "bot_activity", "data": entry})
            print(f"[AutoTrader] SELL {symbol} — {reason}")
        except Exception as e:
            print(f"[AutoTrader] close_long {symbol}: {e}")

    async def _open_short(self, symbol, qty, price, reasons, style, manager, extended=False):
        try:
            if extended:
                limit  = round(price * 0.998, 2)
                result = await self.alpaca.place_order(symbol, qty, "sell", "limit", limit_price=limit, extended_hours=True)
            else:
                result = await self.alpaca.place_order(symbol, qty, "sell", "market")
            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "SHORT", "symbol": symbol,
                "qty": qty, "price": round(price, 2),
                "reasons": reasons, "style": style,
                "order_id": result.get("id"), "extended": extended,
            }
            self._log(entry)
            await manager.broadcast({"type": "bot_activity", "data": entry})
            print(f"[AutoTrader] SHORT {qty} {symbol} @ ${price:.2f} [{style}] — {reasons}")
        except Exception as e:
            print(f"[AutoTrader] open_short {symbol}: {e}")

    async def _cover_short(self, symbol, qty, reason, manager):
        try:
            result = await self.alpaca.place_order(symbol, abs(float(qty)), "buy", "market")
            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "COVER", "symbol": symbol,
                "qty": abs(float(qty)), "reason": reason, "order_id": result.get("id"),
            }
            self._log(entry)
            await manager.broadcast({"type": "bot_activity", "data": entry})
            print(f"[AutoTrader] COVER {symbol} — {reason}")
        except Exception as e:
            print(f"[AutoTrader] cover_short {symbol}: {e}")
