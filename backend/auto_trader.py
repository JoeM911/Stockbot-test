"""
Autonomous trader: scans the universe every 60s, buys/shorts top signals,
exits at stop-loss or take-profit. Supports long-only, short-only, or both.
Conviction score (1-3) scales position size. Extended hours via limit orders.
"""
import asyncio
from datetime import datetime, timezone
from typing import List

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None


class AutoTrader:
    def __init__(self, alpaca_client, scanner, sentiment=None):
        self.alpaca    = alpaca_client
        self.scanner   = scanner
        self.sentiment = sentiment
        self.enabled   = True
        self.mode      = "both"      # "long", "short", or "both"
        self.aggression    = 5
        self.max_positions = 5
        self.risk_pct      = 0.05
        self.max_trade_usd = 10_000
        self.stop_pct      = 0.03
        self.target_pct    = 0.06
        self.portfolio_target: float | None = None
        self.activity: List[dict] = []

    # ------------------------------------------------------------------ public

    @staticmethod
    def session_type() -> str:
        if _ET:
            now = datetime.now(_ET)
        else:
            from datetime import timedelta
            now = datetime.now(timezone(timedelta(hours=-4)))
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

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def get_status(self) -> dict:
        return {
            "enabled":          self.enabled,
            "mode":             self.mode,
            "aggression":       self.aggression,
            "max_positions":    self.max_positions,
            "risk_pct":         self.risk_pct,
            "stop_pct":         self.stop_pct,
            "target_pct":       self.target_pct,
            "max_trade_usd":    self.max_trade_usd,
            "portfolio_target": self.portfolio_target,
            "activity":         self.activity[:30],
        }

    async def run(self, universe: List[str], manager) -> None:
        if not self.enabled:
            return
        session = self.session_type()
        if session == "closed":
            return
        extended = session in ("pre_market", "after_hours")

        try:
            account      = await self.alpaca.get_account()
            positions    = await self.alpaca.get_positions()
            buying_power = float(account["buying_power"])
            equity       = float(account.get("equity") or account.get("portfolio_value") or 0)

            # Separate long and short positions
            longs  = {p["symbol"]: p for p in positions if float(p["qty"]) > 0}
            shorts = {p["symbol"]: p for p in positions if float(p["qty"]) < 0}
            held   = {p["symbol"]: p for p in positions}

            # ---- EXIT longs: stop-loss or take-profit -----------------------
            for sym, pos in list(longs.items()):
                entry   = float(pos["avg_entry_price"])
                current = float(pos["current_price"])
                if entry <= 0: continue
                pnl_pct = (current - entry) / entry
                if pnl_pct <= -self.stop_pct:
                    await self._close_long(sym, pos["qty"], f"Stop loss {pnl_pct*100:.1f}%", manager)
                    del held[sym]
                elif pnl_pct >= self.target_pct:
                    await self._close_long(sym, pos["qty"], f"Take profit +{pnl_pct*100:.1f}%", manager)
                    del held[sym]

            # ---- EXIT shorts: stop-loss or take-profit ----------------------
            # For shorts: profit when price falls, loss when price rises
            for sym, pos in list(shorts.items()):
                entry   = float(pos["avg_entry_price"])
                current = float(pos["current_price"])
                if entry <= 0: continue
                pnl_pct = (entry - current) / entry   # inverted for shorts
                if pnl_pct <= -self.stop_pct:
                    await self._cover_short(sym, pos["qty"], f"Short stop loss {pnl_pct*100:.1f}%", manager)
                    del held[sym]
                elif pnl_pct >= self.target_pct:
                    await self._cover_short(sym, pos["qty"], f"Short take profit +{pnl_pct*100:.1f}%", manager)
                    del held[sym]

            # ---- Portfolio target: halt new entries if goal reached ----------
            if self.portfolio_target and equity >= self.portfolio_target:
                return

            if len(held) >= self.max_positions:
                return

            # ---- Scan for signals -------------------------------------------
            signals = await self.scanner.scan(universe)

            # Filter by mode and availability
            long_candidates  = [s for s in signals if s["action"] == "BUY"   and s["symbol"] not in held]
            short_candidates = [s for s in signals if s["action"] == "SHORT" and s["symbol"] not in held]

            if self.mode == "long":  short_candidates = []
            if self.mode == "short": long_candidates  = []

            if not long_candidates and not short_candidates:
                return

            # ---- Sentiment boost -------------------------------------------
            all_candidates = long_candidates + short_candidates
            sent_map: dict = {}
            if self.sentiment:
                try:
                    syms = [c["symbol"] for c in all_candidates[:10]]
                    sent_scores = await self.sentiment.scan_sentiment(syms)
                    sent_map = {s["symbol"]: s["score"] for s in sent_scores}
                except Exception:
                    pass

            def rank_long(sig):
                tech   = abs(sig.get("change_pct", 0)) + sig.get("conviction", 1) * 2
                social = sent_map.get(sig["symbol"], 0)
                return tech + social * 2

            def rank_short(sig):
                tech   = abs(sig.get("change_pct", 0)) + sig.get("conviction", 1) * 2
                social = -sent_map.get(sig["symbol"], 0)   # bearish sentiment helps shorts
                return tech + social * 2

            long_candidates.sort(key=rank_long,   reverse=True)
            short_candidates.sort(key=rank_short, reverse=True)

            # Pick best long or short based on conviction
            best_long  = long_candidates[0]  if long_candidates  else None
            best_short = short_candidates[0] if short_candidates else None

            # Block long if strongly bearish sentiment, block short if strongly bullish
            if best_long  and sent_map.get(best_long["symbol"],  0) < -0.3: best_long  = None
            if best_short and sent_map.get(best_short["symbol"], 0) >  0.3: best_short = None

            # Choose: pick whichever has higher conviction; prefer long on tie
            pick = None
            if best_long and best_short:
                pick = best_long if best_long.get("conviction", 1) >= best_short.get("conviction", 1) else best_short
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
            if price <= 0:
                return

            reasons = list(pick["signals"])
            s_score = sent_map.get(sym)
            if s_score is not None:
                pct = round(abs(s_score) * 100)
                reasons.append(f"{'Bullish' if s_score > 0 else 'Bearish'} sentiment {pct}%")

            # Conviction scales position: 1x / 1.5x / 2x (capped at max_trade_usd)
            conviction_scale = {1: 1.0, 2: 1.5, 3: 2.0}.get(conviction, 1.0)

            # Scale down near portfolio target
            target_scale = 1.0
            if self.portfolio_target and equity > 0:
                if equity / self.portfolio_target >= 0.90:
                    target_scale = 0.5

            risk      = self.risk_pct * (0.5 if extended else 1.0) * target_scale * conviction_scale
            trade_usd = min(buying_power * risk, self.max_trade_usd * conviction_scale)
            qty       = max(1, int(trade_usd / price))

            if extended:
                reasons.append("Pre-market" if session == "pre_market" else "After-hours")

            reasons.append(f"Conviction {conviction}/3")

            if action == "BUY":
                await self._open_long(sym, qty, price, reasons, manager, extended=extended)
            else:
                await self._open_short(sym, qty, price, reasons, manager, extended=extended)

        except Exception as e:
            print(f"[AutoTrader] {e}")

    # ----------------------------------------------------------------- private

    def _log(self, entry: dict):
        self.activity.insert(0, entry)
        self.activity = self.activity[:100]

    async def _open_long(self, symbol, qty, price, reasons, manager, extended=False):
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
                "reasons": reasons, "order_id": result.get("id"), "extended": extended,
            }
            self._log(entry)
            await manager.broadcast({"type": "bot_activity", "data": entry})
            print(f"[AutoTrader] BUY {qty} {symbol} @ ${price:.2f} — {reasons}")
        except Exception as e:
            print(f"[AutoTrader] open_long {symbol}: {e}")

    async def _close_long(self, symbol, qty, reason, manager):
        try:
            session  = self.session_type()
            extended = session in ("pre_market", "after_hours")
            if extended:
                result = await self.alpaca.place_order(symbol, abs(float(qty)), "sell", "limit", limit_price=None, extended_hours=True, use_current_price=True)
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

    async def _open_short(self, symbol, qty, price, reasons, manager, extended=False):
        try:
            # Short = sell shares we don't own
            if extended:
                limit  = round(price * 0.998, 2)   # slightly below market for short limit
                result = await self.alpaca.place_order(symbol, qty, "sell", "limit", limit_price=limit, extended_hours=True)
            else:
                result = await self.alpaca.place_order(symbol, qty, "sell", "market")
            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "SHORT", "symbol": symbol,
                "qty": qty, "price": round(price, 2),
                "reasons": reasons, "order_id": result.get("id"), "extended": extended,
            }
            self._log(entry)
            await manager.broadcast({"type": "bot_activity", "data": entry})
            print(f"[AutoTrader] SHORT {qty} {symbol} @ ${price:.2f} — {reasons}")
        except Exception as e:
            print(f"[AutoTrader] open_short {symbol}: {e}")

    async def _cover_short(self, symbol, qty, reason, manager):
        try:
            # Cover = buy back to close short position
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
