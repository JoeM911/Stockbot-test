"""
Autonomous trader: scans the universe every 60s, buys top signals,
exits at stop-loss (-3%) or take-profit (+6%). Max 5 open positions.
"""
import asyncio
from datetime import datetime, timezone
from typing import List


class AutoTrader:
    def __init__(self, alpaca_client, scanner, sentiment=None):
        self.alpaca = alpaca_client
        self.scanner = scanner
        self.sentiment = sentiment
        self.enabled = True
        self.max_positions = 5
        self.risk_pct = 0.05       # 5% of buying power per trade
        self.max_trade_usd = 10_000
        self.stop_pct = 0.03       # -3% stop loss
        self.target_pct = 0.06     # +6% take profit (2:1)
        self.activity: List[dict] = []

    # ------------------------------------------------------------------ public

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def get_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "max_positions": self.max_positions,
            "risk_pct": self.risk_pct,
            "stop_pct": self.stop_pct,
            "target_pct": self.target_pct,
            "activity": self.activity[:30],
        }

    async def run(self, universe: List[str], manager) -> None:
        if not self.enabled:
            return
        if not self._market_open():
            return

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

            trade_usd = min(buying_power * self.risk_pct, self.max_trade_usd)
            qty = max(1, int(trade_usd / price))
            await self._enter(sym, qty, price, reasons, manager)

        except Exception as e:
            print(f"[AutoTrader] {e}")

    # ----------------------------------------------------------------- private

    def _market_open(self) -> bool:
        now = datetime.now(timezone.utc)
        if now.weekday() >= 5:          # weekend
            return False
        h, m = now.hour, now.minute
        open_mins  = 14 * 60 + 30       # 09:30 ET = 14:30 UTC
        close_mins = 20 * 60 + 45       # 15:45 ET = 20:45 UTC
        cur_mins   = h * 60 + m
        return open_mins <= cur_mins <= close_mins

    def _log(self, entry: dict):
        self.activity.insert(0, entry)
        self.activity = self.activity[:100]

    async def _enter(self, symbol, qty, price, reasons, manager):
        try:
            result = await self.alpaca.place_order(symbol, qty, "buy", "market")
            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "BUY",
                "symbol": symbol,
                "qty": qty,
                "price": round(price, 2),
                "reasons": reasons,
                "order_id": result.get("id"),
            }
            self._log(entry)
            await manager.broadcast({"type": "bot_activity", "data": entry})
            print(f"[AutoTrader] BUY {qty} {symbol} @ ${price:.2f} — {reasons}")
        except Exception as e:
            print(f"[AutoTrader] entry {symbol}: {e}")

    async def _exit(self, symbol, qty, reason, manager):
        try:
            result = await self.alpaca.place_order(
                symbol, abs(float(qty)), "sell", "market"
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
