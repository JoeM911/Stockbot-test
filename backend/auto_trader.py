"""
Autonomous trader: scans the universe every 60s, buys top signals,
exits at stop-loss (-3%) or take-profit (+6%). Max 5 open positions.
Supports regular hours (market orders) and extended hours (limit orders).
"""
import asyncio
from datetime import datetime, timezone
from typing import List

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None  # Windows without tzdata — fall back to UTC-offset estimate


class AutoTrader:
    def __init__(self, alpaca_client, scanner, sentiment=None):
        self.alpaca = alpaca_client
        self.scanner = scanner
        self.sentiment = sentiment
        self.enabled = True
        self.aggression = 5        # 1 (safe) → 10 (yolo)
        self.max_positions = 5
        self.risk_pct = 0.05       # 5% of buying power per trade
        self.max_trade_usd = 10_000
        self.stop_pct = 0.03       # -3% stop loss
        self.target_pct = 0.06     # +6% take profit (2:1)
        self.portfolio_target: float | None = None  # account value goal
        self.activity: List[dict] = []

    # ------------------------------------------------------------------ public

    @staticmethod
    def session_type() -> str:
        """Returns 'regular', 'pre_market', 'after_hours', or 'closed'."""
        if _ET:
            now = datetime.now(_ET)
        else:
            # Rough UTC fallback (assumes EDT, UTC-4)
            from datetime import timezone, timedelta
            now = datetime.now(timezone(timedelta(hours=-4)))

        if now.weekday() >= 5:
            return "closed"

        h, m = now.hour, now.minute
        mins = h * 60 + m

        if 4 * 60 <= mins < 9 * 60 + 30:
            return "pre_market"
        if 9 * 60 + 30 <= mins < 16 * 60:
            return "regular"
        if 16 * 60 <= mins < 20 * 60:
            return "after_hours"
        return "closed"

    def set_aggression(self, level: int):
        """Map 1-10 aggression level to trading parameters."""
        self.aggression = level
        t = (level - 1) / 9.0  # 0.0 → 1.0
        self.risk_pct      = round(0.02 + t * 0.13, 3)   # 2% → 15%
        self.stop_pct      = round(0.02 + t * 0.04, 3)   # 2% → 6%
        self.target_pct    = round(0.04 + t * 0.10, 3)   # 4% → 14%
        self.max_positions = max(2, round(3 + t * 7))     # 3  → 10
        self.max_trade_usd = round(5_000 + t * 45_000)   # $5k → $50k

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def get_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "aggression": self.aggression,
            "max_positions": self.max_positions,
            "risk_pct": self.risk_pct,
            "stop_pct": self.stop_pct,
            "target_pct": self.target_pct,
            "max_trade_usd": self.max_trade_usd,
            "portfolio_target": self.portfolio_target,
            "activity": self.activity[:30],
        }

    async def run(self, universe: List[str], manager) -> None:
        if not self.enabled:
            return
        session = self.session_type()
        if session == "closed":
            return
        extended = session in ("pre_market", "after_hours")

        try:
            account = await self.alpaca.get_account()
            positions = await self.alpaca.get_positions()
            buying_power = float(account["buying_power"])
            held = {p["symbol"]: p for p in positions}

            # ---- EXIT: check stops and targets on current positions ----------
            for sym, pos in list(held.items()):
                entry = float(pos["avg_entry_price"])
                current = float(pos["current_price"])
                if entry <= 0:
                    continue
                pnl_pct = (current - entry) / entry
                if pnl_pct <= -self.stop_pct:
                    await self._exit(sym, pos["qty"],
                                     f"Stop loss {pnl_pct*100:.1f}%", manager)
                    del held[sym]
                elif pnl_pct >= self.target_pct:
                    await self._exit(sym, pos["qty"],
                                     f"Take profit +{pnl_pct*100:.1f}%", manager)
                    del held[sym]

            # ---- PORTFOLIO TARGET: halt entries if goal reached -------------
            equity = float(account.get("equity") or account.get("portfolio_value") or 0)
            if self.portfolio_target and equity >= self.portfolio_target:
                return  # goal reached — don't open new positions

            # ---- ENTRY: find best signal not already held -------------------
            if len(held) >= self.max_positions:
                return

            signals = await self.scanner.scan(universe)
            candidates = [
                s for s in signals
                if s["action"] == "BUY" and s["symbol"] not in held
            ]
            if not candidates:
                return

            # Boost score with sentiment — prefer stocks with bullish social signal
            sent_map: dict = {}
            if self.sentiment:
                try:
                    syms = [c["symbol"] for c in candidates[:10]]
                    sent_scores = await self.sentiment.scan_sentiment(syms)
                    sent_map = {s["symbol"]: s["score"] for s in sent_scores}
                except Exception:
                    pass

            def rank(sig):
                tech_score = abs(sig.get("change_pct", 0)) + (1 if sig.get("rsi", 50) < 35 else 0)
                social_score = sent_map.get(sig["symbol"], 0)
                return tech_score + social_score * 2  # social counts double

            candidates.sort(key=rank, reverse=True)
            best = candidates[0]

            # Skip if sentiment is strongly bearish (score < -0.3)
            if sent_map.get(best["symbol"], 0) < -0.3:
                return

            sym   = best["symbol"]
            price = best["price"]
            if price <= 0:
                return

            reasons = list(best["signals"])
            s_score = sent_map.get(sym)
            if s_score is not None:
                pct = round(abs(s_score) * 100)
                reasons.append(f"{'Bullish' if s_score > 0 else 'Bearish'} sentiment {pct}%")

            # Scale down position size when close to portfolio target (within 10%)
            target_scale = 1.0
            if self.portfolio_target and equity > 0:
                pct_of_goal = equity / self.portfolio_target
                if pct_of_goal >= 0.90:
                    target_scale = 0.5  # half size in final 10% — protect gains

            # Halve position size in extended hours (wider spreads, less liquidity)
            risk = self.risk_pct * (0.5 if extended else 1.0) * target_scale
            trade_usd = min(buying_power * risk, self.max_trade_usd)
            qty = max(1, int(trade_usd / price))
            if extended:
                reasons.append(f"{'Pre-market' if session == 'pre_market' else 'After-hours'} session")
            await self._enter(sym, qty, price, reasons, manager, extended=extended)

        except Exception as e:
            print(f"[AutoTrader] {e}")

    # ----------------------------------------------------------------- private

    def _log(self, entry: dict):
        self.activity.insert(0, entry)
        self.activity = self.activity[:100]

    async def _enter(self, symbol, qty, price, reasons, manager, extended=False):
        try:
            if extended:
                # Extended hours require limit orders; buy slightly above market
                limit = round(price * 1.002, 2)
                result = await self.alpaca.place_order(
                    symbol, qty, "buy", "limit",
                    limit_price=limit, extended_hours=True,
                )
            else:
                result = await self.alpaca.place_order(symbol, qty, "buy", "market")
            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "BUY",
                "symbol": symbol,
                "qty": qty,
                "price": round(price, 2),
                "reasons": reasons,
                "order_id": result.get("id"),
                "extended": extended,
            }
            self._log(entry)
            await manager.broadcast({"type": "bot_activity", "data": entry})
            print(f"[AutoTrader] BUY {qty} {symbol} @ ${price:.2f} {'(ext)' if extended else ''} — {reasons}")
        except Exception as e:
            print(f"[AutoTrader] entry {symbol}: {e}")

    async def _exit(self, symbol, qty, reason, manager):
        try:
            session = self.session_type()
            extended = session in ("pre_market", "after_hours")
            qty_f = abs(float(qty))
            if extended:
                # Get approximate current price from position (passed as qty arg)
                # Use a wide limit to ensure fill
                result = await self.alpaca.place_order(
                    symbol, qty_f, "sell", "limit",
                    limit_price=None, extended_hours=True, use_current_price=True,
                )
            else:
                result = await self.alpaca.place_order(
                    symbol, qty_f, "sell", "market"
                )
            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "SELL",
                "symbol": symbol,
                "qty": abs(float(qty)),
                "reason": reason,
                "order_id": result.get("id"),
            }
            self._log(entry)
            await manager.broadcast({"type": "bot_activity", "data": entry})
            print(f"[AutoTrader] SELL {symbol} — {reason}")
        except Exception as e:
            print(f"[AutoTrader] exit {symbol}: {e}")
