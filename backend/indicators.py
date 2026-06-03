from typing import List, Dict
import numpy as np
import pandas as pd


def compute_indicators(bars: List[dict]) -> dict:
    if len(bars) < 30:
        return {}

    df = pd.DataFrame(bars)
    closes = df["close"]
    highs = df["high"]
    lows = df["low"]
    volumes = df["volume"]
    times = df["time"].tolist()

    # EMAs
    ema9 = closes.ewm(span=9, adjust=False).mean()
    ema21 = closes.ewm(span=21, adjust=False).mean()
    ema50 = closes.ewm(span=50, adjust=False).mean()
    ema200 = closes.ewm(span=200, adjust=False).mean()

    # Bollinger Bands
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20

    # RSI
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # MACD
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal

    # VWAP
    typical = (highs + lows + closes) / 3
    vwap = (typical * volumes).cumsum() / volumes.cumsum()

    # ATR
    hl = highs - lows
    hc = (highs - closes.shift(1)).abs()
    lc = (lows - closes.shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    def to_series(s: pd.Series) -> List[dict]:
        return [
            {"time": int(t), "value": round(float(v), 4)}
            for t, v in zip(times, s)
            if pd.notna(v) and not np.isinf(v)
        ]

    def safe_last(s: pd.Series, decimals: int = 4):
        v = s.iloc[-1]
        return round(float(v), decimals) if pd.notna(v) and not np.isinf(v) else None

    return {
        "ema9": to_series(ema9),
        "ema21": to_series(ema21),
        "ema50": to_series(ema50),
        "ema200": to_series(ema200),
        "bb_upper": to_series(bb_upper),
        "bb_lower": to_series(bb_lower),
        "bb_middle": to_series(sma20),
        "rsi": to_series(rsi),
        "macd": to_series(macd),
        "macd_signal": to_series(macd_signal),
        "macd_hist": to_series(macd_hist),
        "vwap": to_series(vwap),
        "atr": to_series(atr),
        "current": {
            "rsi": safe_last(rsi, 2),
            "macd": safe_last(macd, 4),
            "macd_signal": safe_last(macd_signal, 4),
            "atr": safe_last(atr, 4),
            "ema9": safe_last(ema9, 4),
            "ema21": safe_last(ema21, 4),
            "ema50": safe_last(ema50, 4),
            "vwap": safe_last(vwap, 4),
            "bb_upper": safe_last(bb_upper, 4),
            "bb_lower": safe_last(bb_lower, 4),
        },
    }
