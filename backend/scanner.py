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

    async def scan_intraday(self, symbols: List[str]) -> List[dict]:
        results = await asyncio.gather(
            *[self._check_intraday(s) for s in symbols], return_exceptions=True
        )
        signals = [r for r in results if isinstance(r, dict)]
        return sorted(signals, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)

    async def _check_intraday(self, symbol: str) -> dict | None:
        try:
            bars = await self.alpaca.get_bars(symbol, "5m", 78)  # ~1 trading day of 5m bars
            if len(bars) < 20:
                return None

            df      = pd.DataFrame(bars)
            closes  = df["close"]
            volumes = df["volume"]
            highs   = df["high"]
            lows    = df["low"]

            current_price = float(closes.iloc[-1])
            prev_price    = float(closes.iloc[-2])
            pct_change    = (current_price - prev_price) / prev_price * 100

            current_vol = float(volumes.iloc[-1])
            avg_vol     = float(volumes.rolling(20).mean().iloc[-1])
            vol_spike   = avg_vol > 0 and current_vol > avg_vol * 2

            # VWAP
            typical   = (highs + lows + closes) / 3
            vwap_vals = (typical * volumes).cumsum() / volumes.cumsum()
            vwap      = float(vwap_vals.iloc[-1])
            prev_vwap = float(vwap_vals.iloc[-2])
            crossed_above = float(closes.iloc[-2]) <= prev_vwap and current_price > vwap
            crossed_below = float(closes.iloc[-2]) >= prev_vwap and current_price < vwap
            above_vwap    = current_price > vwap

            # RSI on 5m
            delta = closes.diff()
            gain  = delta.where(delta > 0, 0).rolling(14).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs    = gain / loss.replace(0, np.nan)
            rsi_s = 100 - (100 / (1 + rs))
            rsi   = float(rsi_s.iloc[-1]) if pd.notna(rsi_s.iloc[-1]) else None

            # EMA 9/21 on 5m
            ema9  = closes.ewm(span=9,  adjust=False).mean()
            ema21 = closes.ewm(span=21, adjust=False).mean()
            ema_bull = float(ema9.iloc[-2]) < float(ema21.iloc[-2]) and float(ema9.iloc[-1]) > float(ema21.iloc[-1])
            ema_bear = float(ema9.iloc[-2]) > float(ema21.iloc[-2]) and float(ema9.iloc[-1]) < float(ema21.iloc[-1])

            big_up   = pct_change > 0.5
            big_down = pct_change < -0.5

            bull_signals = []
            if crossed_above:
                bull_signals.append("VWAP Cross Up")
            if rsi is not None and rsi < 35:
                bull_signals.append("RSI Oversold 5m")
            if ema_bull:
                bull_signals.append("EMA Bull Cross 5m")
            if vol_spike and big_up:
                bull_signals.append("Vol Spike Up 5m")
            if above_vwap and ema_bull and not crossed_above:
                bull_signals.append("EMA+VWAP Bull")

            bear_signals = []
            if crossed_below:
                bear_signals.append("VWAP Cross Down")
            if rsi is not None and rsi > 65:
                bear_signals.append("RSI Overbought 5m")
            if ema_bear:
                bear_signals.append("EMA Bear Cross 5m")
            if vol_spike and big_down:
                bear_signals.append("Vol Spike Down 5m")
            if not above_vwap and ema_bear and not crossed_below:
                bear_signals.append("EMA+VWAP Bear")

            if not bull_signals and not bear_signals:
                return None

            if len(bull_signals) >= len(bear_signals):
                action     = "BUY"
                signals    = bull_signals
                conviction = min(3, len(bull_signals))
            else:
                action     = "SHORT"
                signals    = bear_signals
                conviction = min(3, len(bear_signals))

            return {
                "symbol":       symbol,
                "price":        round(current_price, 2),
                "change_pct":   round(pct_change, 2),
                "rsi":          round(rsi, 1) if rsi else None,
                "volume_ratio": round(current_vol / avg_vol, 1) if avg_vol else 0,
                "signals":      signals,
                "action":       action,
                "conviction":   conviction,
                "timeframe":    "5m",
            }
        except Exception as e:
            print(f"Scanner intraday [{symbol}] error: {e}")
            return None

    async def _check(self, symbol: str) -> dict | None:
        try:
            bars = await self.alpaca.get_bars(symbol, "1D", 60)
            if len(bars) < 22:
                return None

            df = pd.DataFrame(bars)
            closes = df["close"]
            volumes = df["volume"]

            current_price = float(closes.iloc[-1])
            prev_price    = float(closes.iloc[-2])
            current_vol   = float(volumes.iloc[-1])
            avg_vol       = float(volumes.rolling(20).mean().iloc[-1])
            pct_change    = (current_price - prev_price) / prev_price * 100

            # RSI
            delta = closes.diff()
            gain  = delta.where(delta > 0, 0).rolling(14).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs    = gain / loss.replace(0, np.nan)
            rsi_series = 100 - (100 / (1 + rs))
            rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else None

            # EMA crossover
            ema9  = closes.ewm(span=9,  adjust=False).mean()
            ema21 = closes.ewm(span=21, adjust=False).mean()
            ema_cross_bull = float(ema9.iloc[-2]) < float(ema21.iloc[-2]) and float(ema9.iloc[-1]) > float(ema21.iloc[-1])
            ema_cross_bear = float(ema9.iloc[-2]) > float(ema21.iloc[-2]) and float(ema9.iloc[-1]) < float(ema21.iloc[-1])

            # Bollinger Band squeeze
            sma20    = closes.rolling(20).mean()
            std20    = closes.rolling(20).std()
            bb_width = (4 * std20.iloc[-1]) / sma20.iloc[-1] * 100
            bb_squeeze = bb_width < 5

            # 50-day high/low
            at_50d_high = current_price >= float(closes.rolling(50).max().iloc[-1])
            at_50d_low  = current_price <= float(closes.rolling(50).min().iloc[-1])

            vol_spike = avg_vol > 0 and current_vol > avg_vol * 2
            big_up    = pct_change > 3
            big_down  = pct_change < -3

            # ── Build bullish signals ──────────────────────────────────────
            bull_signals = []
            if rsi is not None and rsi < 30:
                bull_signals.append("RSI Oversold" if rsi >= 25 else "RSI Extremely Oversold")
            if ema_cross_bull:
                bull_signals.append("EMA Bullish Cross")
            if vol_spike and big_up:
                bull_signals.append("Vol Spike 2x+ Up")
            elif vol_spike:
                bull_signals.append("Vol Spike 2x+")
            if at_50d_high:
                bull_signals.append("50D High")
            if bb_squeeze:
                bull_signals.append("BB Squeeze")
            if big_up and not vol_spike:
                bull_signals.append(f"Up {pct_change:.1f}%")

            # ── Build bearish signals ──────────────────────────────────────
            bear_signals = []
            if rsi is not None and rsi > 70:
                bear_signals.append("RSI Overbought" if rsi <= 75 else "RSI Extremely Overbought")
            if ema_cross_bear:
                bear_signals.append("EMA Bearish Cross")
            if vol_spike and big_down:
                bear_signals.append("Vol Spike 2x+ Down")
            if at_50d_low:
                bear_signals.append("50D Low")
            if big_down and not vol_spike:
                bear_signals.append(f"Down {pct_change:.1f}%")

            if not bull_signals and not bear_signals:
                return None

            # ── Determine action & conviction ──────────────────────────────
            # Conviction 1 = weak (1 signal), 2 = moderate, 3 = strong (3+ signals)
            if len(bull_signals) >= len(bear_signals):
                action     = "BUY"  if len(bull_signals) >= 1 else "WATCH"
                signals    = bull_signals
                conviction = min(3, len(bull_signals))
            else:
                action     = "SHORT" if len(bear_signals) >= 1 else "WATCH"
                signals    = bear_signals
                conviction = min(3, len(bear_signals))

            # BB squeeze alone is never enough to act — just watch
            if signals == ["BB Squeeze"]:
                action     = "WATCH"
                conviction = 1

            return {
                "symbol":       symbol,
                "price":        round(current_price, 2),
                "change_pct":   round(pct_change, 2),
                "rsi":          round(rsi, 1) if rsi else None,
                "volume_ratio": round(current_vol / avg_vol, 1) if avg_vol else 0,
                "signals":      signals,
                "action":       action,
                "conviction":   conviction,
            }
        except Exception as e:
            print(f"Scanner [{symbol}] error: {e}")
            return None
