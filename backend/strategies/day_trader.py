import asyncio
from datetime import datetime, timezone
from typing import List
import numpy as np
import pandas as pd


class DayTrader:
    """
    Opening Range Breakout (ORB) + VWAP strategy.
    - Establishes the opening range from the first 30 min of trading
    - Enters when price breaks above OR high with volume confirmation and above VWAP
    - Stop: OR low | Target: 2x risk from OR high
    - All positions auto-closed 15 min before market close
    """

    def __init__(self, alpaca_client):
        self.alpaca = alpaca_client
        self.opening_ranges: dict = {}
        self.traded_today: set = set()
        self._last_reset_date: str = ""

    def _market_info(self):
        now = datetime.now(timezone.utc)
        if now.weekday() >= 5:
            return False, 0
        minutes_since_open = (now.hour * 60 + now.minute) - (14 * 60 + 30)
        minutes_to_close = (21 * 60) - (now.hour * 60 + now.minute)
        is_open = 0 <= minutes_since_open and minutes_to_close > 0
        return is_open, minutes_to_close

    async def run(self, symbols: List[str]):
        is_open, minutes_to_close = self._market_info()
        if not is_open:
            return

        # Reset state at start of new trading day
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self._last_reset_date:
            self.opening_ranges.clear()
            self.traded_today.clear()
            self._last_reset_date = today

        # Force-close all intraday positions 15 min before close
        if minutes_to_close <= 15:
            positions = await self.alpaca.get_positions()
            for pos in positions:
                if pos["symbol"] in self.traded_today:
                    qty = abs(pos["qty"])
                    await self.alpaca.place_order(pos["symbol"], qty, "sell", "market")
                    print(f"[DayTrader] EOD close: {qty} {pos['symbol']}")
            return

        await asyncio.gather(*[self._check(s) for s in symbols], return_exceptions=True)

    async def _check(self, symbol: str):
        try:
            bars = await self.alpaca.get_bars(symbol, "5m", 80)
            if len(bars) < 8:
                return

            df = pd.DataFrame(bars)
            now = datetime.now(timezone.utc)
            minutes_since_open = (now.hour * 60 + now.minute) - (14 * 60 + 30)

            if minutes_since_open >= 30 and symbol not in self.opening_ranges:
                or_bars = df.head(6)
                self.opening_ranges[symbol] = {
                    "high": float(or_bars["high"].max()),
                    "low": float(or_bars["low"].min()),
                }

            if symbol not in self.opening_ranges:
                return

            or_high = self.opening_ranges[symbol]["high"]
            or_low = self.opening_ranges[symbol]["low"]
            current = df.iloc[-1]
            current_price = float(current["close"])
            current_vol = float(current["volume"])
            avg_vol = float(df["volume"].mean())

            # VWAP
            typical = (df["high"] + df["low"] + df["close"]) / 3
            vwap = float((typical * df["volume"]).cumsum().iloc[-1] / df["volume"].cumsum().iloc[-1])

            positions = await self.alpaca.get_positions()
            pos_map = {p["symbol"]: p for p in positions}

            if (
                symbol not in pos_map and
                symbol not in self.traded_today and
                current_price > or_high and
                current_vol > avg_vol * 1.5 and
                current_price > vwap
            ):
                account = await self.alpaca.get_account()
                buying_power = account["buying_power"]
                stop_dist = current_price - or_low
                if stop_dist <= 0:
                    return
                risk = buying_power * 0.02
                qty = max(1, int(risk / stop_dist))
                qty = min(qty, int(buying_power * 0.1 / current_price))
                if qty < 1:
                    return

                await self.alpaca.place_order(symbol, qty, "buy", "market")
                self.traded_today.add(symbol)
                print(f"[DayTrader] BUY {qty} {symbol} @ {current_price:.2f} | OR:{or_low:.2f}-{or_high:.2f}")

            elif symbol in pos_map:
                pos = pos_map[symbol]
                entry = pos["avg_entry_price"]
                stop_price = max(or_low, entry * 0.98)
                target_price = entry + 2 * (entry - or_low)

                if current_price <= stop_price or current_price >= target_price or current_price < vwap:
                    qty = abs(pos["qty"])
                    await self.alpaca.place_order(symbol, qty, "sell", "market")
                    print(f"[DayTrader] SELL {qty} {symbol} @ {current_price:.2f}")

        except Exception as e:
            print(f"[DayTrader] {symbol} error: {e}")
