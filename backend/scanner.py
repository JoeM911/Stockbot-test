import asyncio
from typing import List
import numpy as np
import pandas as pd


class Scanner:
    def __init__(self, alpaca_client):
        self.alpaca = alpaca_client

    async def scan(self, symbols: List[str]) -> List[dict]:
        results = await asyncio.gather(
            *[self._check(s) for s in symbols], return_exceptions=True
        )
        signals = [r for r in results if isinstance(r, dict)]
        return sorted(signals, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)

    async def _check(self, symbol: str) -> dict | None:
        try:
            bars = await self.alpaca.get_bars(symbol, "1D", 60)
            if len(bars) < 22:
                return None

            df = pd.DataFrame(bars)
            closes = df["close"]
            volumes = df["volume"]

            current_price = float(closes.iloc[-1])
            prev_price = float(closes.iloc[-2])
            current_vol = float(volumes.iloc[-1])
            avg_vol = float(volumes.rolling(20).mean().iloc[-1])

            pct_change = (current_price - prev_price) / prev_price * 100

            # RSI
            delta = closes.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi_series = 100 - (100 / (1 + rs))
            rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else None

            # EMA crossover
            ema9 = closes.ewm(span=9, adjust=False).mean()
            ema21 = closes.ewm(span=21, adjust=False).mean()
            ema_cross_bull = (
                float(ema9.iloc[-2]) < float(ema21.iloc[-2]) and
                float(ema9.iloc[-1]) > float(ema21.iloc[-1])
            )
            ema_cross_bear = (
                float(ema9.iloc[-2]) > float(ema21.iloc[-2]) and
                float(ema9.iloc[-1]) < float(ema21.iloc[-1])
            )

            # BB squeeze: bandwidth < 5% of price
            sma20 = closes.rolling(20).mean()
            std20 = closes.rolling(20).std()
            bb_width = (4 * std20.iloc[-1]) / sma20.iloc[-1] * 100
            bb_squeeze = bb_width < 5

            signal_list = []
            if rsi is not None:
                if rsi < 30:
                    signal_list.append("RSI Oversold")
                elif rsi > 70:
                    signal_list.append("RSI Overbought")

            if ema_cross_bull:
                signal_list.append("EMA Bullish Cross")
            elif ema_cross_bear:
                signal_list.append("EMA Bearish Cross")

            if avg_vol > 0 and current_vol > avg_vol * 2:
                signal_list.append("Vol Spike 2x+")

            if pct_change > 3:
                signal_list.append(f"Up {pct_change:.1f}%")
            elif pct_change < -3:
                signal_list.append(f"Down {pct_change:.1f}%")

            if current_price >= float(closes.rolling(50).max().iloc[-1]):
                signal_list.append("50D High")
            elif current_price <= float(closes.rolling(50).min().iloc[-1]):
                signal_list.append("50D Low")

            if bb_squeeze:
                signal_list.append("BB Squeeze")

            if not signal_list:
                return None

            action = "WATCH"
            if any(s in signal_list for s in ["RSI Oversold", "EMA Bullish Cross"]):
                action = "BUY"
            elif any(s in signal_list for s in ["RSI Overbought", "EMA Bearish Cross"]):
                action = "SELL"

            return {
                "symbol": symbol,
                "price": round(current_price, 2),
                "change_pct": round(pct_change, 2),
                "rsi": round(rsi, 1) if rsi else None,
                "volume_ratio": round(current_vol / avg_vol, 1) if avg_vol else 0,
                "signals": signal_list,
                "action": action,
            }
        except Exception as e:
            print(f"Scanner [{symbol}] error: {e}")
            return None
