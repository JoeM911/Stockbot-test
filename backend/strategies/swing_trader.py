import asyncio
from datetime import datetime, timezone
from typing import List
import numpy as np
import pandas as pd


class SwingTrader:
    """
    EMA 9/21 crossover + RSI strategy for multi-day swing trades.
    - Entry: EMA9 crosses above EMA21, RSI < 65, price above EMA50
    - Exit: EMA9 crosses below EMA21 OR RSI > 75 OR stop/target hit
    - Stop: 3% below entry | Target: 9% above entry (3:1 R:R)
    """

    def __init__(self, alpaca_client):
        self.alpaca = alpaca_client
        self._last_run_date: str = ""

    async def run(self, symbols: List[str]):
        now = datetime.now(timezone.utc)
        if now.weekday() >= 5:
            return
        # Run once per day around market open
        today = now.date().isoformat()
        if today == self._last_run_date:
            return
        if now.hour < 14:
            return
        self._last_run_date = today

        await asyncio.gather(*[self._check(s) for s in symbols], return_exceptions=True)

    async def _check(self, symbol: str):
        try:
            bars = await self.alpaca.get_bars(symbol, "1D", 120)
            if len(bars) < 60:
                return

            df = pd.DataFrame(bars)
            closes = df["close"]
            current_price = float(closes.iloc[-1])

            ema9 = closes.ewm(span=9, adjust=False).mean()
            ema21 = closes.ewm(span=21, adjust=False).mean()
            ema50 = closes.ewm(span=50, adjust=False).mean()

            delta = closes.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi_series = 100 - (100 / (1 + rs))
            rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else None

            ema9_prev, ema9_curr = float(ema9.iloc[-2]), float(ema9.iloc[-1])
            ema21_prev, ema21_curr = float(ema21.iloc[-2]), float(ema21.iloc[-1])

            positions = await self.alpaca.get_positions()
            pos_map = {p["symbol"]: p for p in positions}

            # Entry
            if (
                symbol not in pos_map and
                ema9_prev < ema21_prev and
                ema9_curr > ema21_curr and
                rsi is not None and rsi < 65 and
                current_price > float(ema50.iloc[-1])
            ):
                account = await self.alpaca.get_account()
                buying_power = account["buying_power"]

                # ATR position sizing
                hl = df["high"] - df["low"]
                hc = (df["high"] - closes.shift(1)).abs()
                lc = (df["low"] - closes.shift(1)).abs()
                tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
                atr = float(tr.rolling(14).mean().iloc[-1])

                risk = buying_power * 0.02
                qty = max(1, int(risk / (atr * 2))) if atr > 0 else 1
                qty = min(qty, int(buying_power * 0.15 / current_price))
                if qty < 1:
                    return

                await self.alpaca.place_order(symbol, qty, "buy", "market")
                print(f"[SwingTrader] BUY {qty} {symbol} @ {current_price:.2f} RSI:{rsi:.1f}")

            # Exit
            elif symbol in pos_map:
                pos = pos_map[symbol]
                entry = pos["avg_entry_price"]
                stop = entry * 0.97
                target = entry * 1.09

                sell = (
                    (ema9_prev > ema21_prev and ema9_curr < ema21_curr) or
                    (rsi is not None and rsi > 75) or
                    current_price <= stop or
                    current_price >= target
                )
                if sell:
                    qty = abs(pos["qty"])
                    await self.alpaca.place_order(symbol, qty, "sell", "market")
                    print(f"[SwingTrader] SELL {qty} {symbol} @ {current_price:.2f}")

        except Exception as e:
            print(f"[SwingTrader] {symbol} error: {e}")
