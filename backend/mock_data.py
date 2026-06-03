"""
Mock/demo data provider. Uses real current prices from Yahoo Finance as the
base so the terminal shows accurate prices even without Alpaca keys. If Yahoo
Finance is unavailable, falls back to hardcoded approximate values.
"""
import math
import random
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict

# Fallback prices (used only if yfinance fetch fails)
_FALLBACK = {
    "AAPL": 213.50, "MSFT": 442.80, "NVDA": 137.20, "TSLA": 248.60,
    "GOOGL": 178.40, "META": 612.30, "AMD": 162.10, "SPY": 589.20,
    "QQQ": 511.70, "AMZN": 222.90, "PLTR": 38.40, "SOFI": 14.20,
    "COIN": 264.80,
}

_BASE: Dict[str, float] = {}
_prices: Dict[str, float] = {}
_last_tick = 0.0
_base_loaded = False


def _load_real_prices():
    """Fetch current prices from Yahoo Finance to seed the mock walk."""
    global _BASE, _prices, _base_loaded
    try:
        import yfinance as yf
        symbols = list(_FALLBACK.keys())
        tickers = yf.download(
            " ".join(symbols),
            period="1d",
            interval="1m",
            progress=False,
            auto_adjust=True,
        )
        close = tickers["Close"] if "Close" in tickers.columns.get_level_values(0) else tickers
        fetched = {}
        for sym in symbols:
            try:
                col = close[sym] if sym in close.columns else None
                if col is not None:
                    last = col.dropna().iloc[-1]
                    if last > 0:
                        fetched[sym] = round(float(last), 2)
            except Exception:
                pass
        if fetched:
            _BASE = {**_FALLBACK, **fetched}
            _prices = dict(_BASE)
            _base_loaded = True
            print(f"[mock_data] Loaded {len(fetched)} real prices from Yahoo Finance")
            return
    except Exception as e:
        print(f"[mock_data] Yahoo Finance unavailable ({e}), using fallback prices")

    _BASE = dict(_FALLBACK)
    _prices = dict(_FALLBACK)
    _base_loaded = True


# Load real prices in background so startup isn't blocked
threading.Thread(target=_load_real_prices, daemon=True).start()


def _ensure_loaded():
    """Block briefly if the background price fetch hasn't completed yet."""
    deadline = time.time() + 8
    while not _base_loaded and time.time() < deadline:
        time.sleep(0.05)
    if not _base_loaded:
        # Timed out — use fallback immediately
        global _BASE, _prices
        _BASE = dict(_FALLBACK)
        _prices = dict(_FALLBACK)


def _tick_prices():
    global _last_tick
    _ensure_loaded()
    now = time.time()
    if now - _last_tick < 2:
        return
    _last_tick = now
    for sym in _prices:
        drift = random.gauss(0, 0.0008)
        _prices[sym] = round(_prices[sym] * (1 + drift), 2)


def get_account() -> dict:
    _tick_prices()
    equity = 127_842.50 + random.uniform(-200, 200)
    last_equity = 126_500.00
    pnl = equity - last_equity
    return {
        "equity": round(equity, 2),
        "buying_power": round(equity * 0.8, 2),
        "cash": round(equity * 0.35, 2),
        "portfolio_value": round(equity, 2),
        "day_trade_count": 1,
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl / last_equity * 100, 3),
        "pattern_day_trader": False,
    }


def get_positions() -> List[dict]:
    _tick_prices()
    # Use real prices as entry basis so unrealized P&L isn't absurd
    aapl_entry = round(_BASE.get("AAPL", 213.50) * 0.95, 2)
    nvda_entry  = round(_BASE.get("NVDA", 137.20) * 0.92, 2)
    tsla_entry  = round(_BASE.get("TSLA", 248.60) * 0.97, 2)
    mock_positions = [
        ("AAPL", 50, aapl_entry),
        ("NVDA", 30, nvda_entry),
        ("TSLA", 20, tsla_entry),
    ]
    result = []
    for sym, qty, entry in mock_positions:
        curr = _prices.get(sym, entry)
        pl = (curr - entry) * qty
        plpc = (curr - entry) / entry
        result.append({
            "symbol": sym,
            "qty": float(qty),
            "avg_entry_price": entry,
            "current_price": round(curr, 2),
            "market_value": round(curr * qty, 2),
            "unrealized_pl": round(pl, 2),
            "unrealized_plpc": round(plpc * 100, 3),
            "side": "long",
            "cost_basis": round(entry * qty, 2),
        })
    return result


def get_recent_orders() -> List[dict]:
    _ensure_loaded()
    aapl_p = round(_BASE.get("AAPL", 198.40) * 0.95, 2)
    nvda_p  = round(_BASE.get("NVDA", 118.60) * 0.92, 2)
    tsla_p  = round(_BASE.get("TSLA", 241.80) * 0.97, 2)
    spy_p   = round(_BASE.get("SPY",  588.40) * 0.99, 2)
    orders = [
        ("AAPL", 50, "buy",  "filled",   aapl_p, "2025-06-03T09:32:15Z"),
        ("NVDA", 30, "buy",  "filled",   nvda_p, "2025-06-03T09:45:22Z"),
        ("TSLA", 10, "sell", "filled",   tsla_p, "2025-06-03T11:12:08Z"),
        ("META",  5, "buy",  "canceled", None,   "2025-06-03T13:22:01Z"),
        ("SPY",  10, "buy",  "filled",   spy_p,  "2025-06-02T14:01:55Z"),
    ]
    return [
        {
            "id": f"mock-{i}",
            "symbol": sym,
            "qty": float(qty),
            "filled_qty": float(qty) if status == "filled" else 0.0,
            "side": side,
            "type": "market",
            "status": status,
            "filled_avg_price": price,
            "submitted_at": ts,
        }
        for i, (sym, qty, side, status, price, ts) in enumerate(orders)
    ]


def get_latest_quotes(symbols: List[str]) -> Dict[str, dict]:
    _tick_prices()
    result = {}
    for sym in symbols:
        price = _prices.get(sym, _BASE.get(sym, 100.0))
        spread = price * 0.0001
        result[sym] = {
            "symbol": sym,
            "bid": round(price - spread, 2),
            "ask": round(price + spread, 2),
            "price": round(price, 2),
        }
    return result


def get_bars(symbol: str, timeframe: str = "1D", limit: int = 200) -> List[dict]:
    """Synthetic OHLCV bars seeded from real current price so charts look right."""
    _ensure_loaded()
    base = _BASE.get(symbol, 100.0)
    seed = sum(ord(c) for c in symbol)
    rng = random.Random(seed)

    tf_secs = {
        "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
        "1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800,
    }
    interval = tf_secs.get(timeframe, 86400)

    now = int(datetime.now(timezone.utc).replace(second=0, microsecond=0).timestamp())
    now = (now // interval) * interval

    # Start ~15% below current price and random-walk toward it
    price = base * rng.uniform(0.82, 0.92)
    bars = []

    for i in range(limit, 0, -1):
        ts = now - i * interval
        change = rng.gauss(0.0003, 0.015)
        open_ = price
        close = round(price * (1 + change), 2)
        high = round(max(open_, close) * rng.uniform(1.000, 1.012), 2)
        low  = round(min(open_, close) * rng.uniform(0.988, 1.000), 2)
        volume = round(rng.uniform(8_000_000, 60_000_000))
        bars.append({"time": ts, "open": round(open_, 2), "high": high, "low": low, "close": close, "volume": volume})
        price = close

    return bars


def get_scanner_signals(symbols: List[str]) -> List[dict]:
    _tick_prices()
    signals_map = {
        "NVDA": {"signals": ["RSI Oversold", "Vol Spike 2x+"], "action": "BUY"},
        "TSLA": {"signals": ["EMA Bearish Cross"], "action": "SELL"},
        "AAPL": {"signals": ["BB Squeeze", "50D High"], "action": "WATCH"},
        "META": {"signals": ["EMA Bullish Cross"], "action": "BUY"},
        "COIN": {"signals": ["Up 4.2%", "Vol Spike 2x+"], "action": "BUY"},
        "AMD":  {"signals": ["RSI Overbought"], "action": "SELL"},
        "PLTR": {"signals": ["50D High", "Vol Spike 2x+"], "action": "WATCH"},
        "SPY":  {"signals": ["BB Squeeze"], "action": "WATCH"},
    }
    result = []
    for sym in symbols:
        if sym in signals_map:
            price = _prices.get(sym, _BASE.get(sym, 100.0))
            base  = _BASE.get(sym, price)
            chg   = (price - base) / base * 100
            result.append({
                "symbol": sym,
                "price": round(price, 2),
                "change_pct": round(chg + random.uniform(-1.5, 1.5), 2),
                "rsi": round(random.uniform(28, 72), 1),
                "volume_ratio": round(random.uniform(1.1, 3.2), 1),
                **signals_map[sym],
            })
    return sorted(result, key=lambda x: abs(x["change_pct"]), reverse=True)


def get_portfolio_history(period: str = "1M") -> List[dict]:
    """Generate a realistic equity growth curve for demo mode."""
    _ensure_loaded()
    import random as _r
    period_days = {"1D": 1, "1W": 7, "1M": 30, "3M": 90}.get(period, 30)
    interval = 3600 if period_days <= 1 else 86400
    points = min(period_days * (24 if period_days == 1 else 1), 200)
    now = int(datetime.now(timezone.utc).timestamp())
    now = (now // interval) * interval
    rng = _r.Random(42)
    equity = 120_000.0
    result = []
    for i in range(points, 0, -1):
        ts = now - i * interval
        equity *= 1 + rng.gauss(0.0005, 0.008)
        result.append({"time": ts, "value": round(equity, 2)})
    return result


def get_news(symbols: List[str]) -> List[dict]:
    headlines = [
        ("AAPL", "Apple Intelligence features rolling out to more markets", "Reuters", "positive"),
        ("NVDA", "Nvidia data center revenue surges 400% year-over-year", "Bloomberg", "positive"),
        ("TSLA", "Tesla Cybertruck production ramp faces supply chain headwinds", "WSJ", "negative"),
        ("META", "Meta AI assistant reaches 1 billion monthly active users", "TechCrunch", "positive"),
        ("SPY",  "Fed signals patient approach to rate cuts amid sticky inflation", "FT", "neutral"),
        ("MSFT", "Microsoft Azure growth accelerates on AI workload demand", "CNBC", "positive"),
        ("GOOGL","Alphabet Search revenue beats estimates despite AI competition", "Reuters", "positive"),
        ("COIN", "Coinbase reports record institutional trading volumes in Q2", "Bloomberg", "positive"),
        ("PLTR", "Palantir wins $650M DoD AI contract expansion", "DefenseNews", "positive"),
        ("AMD",  "AMD MI300X GPUs gaining traction among hyperscalers", "AnandTech", "positive"),
    ]
    now = datetime.now(timezone.utc)
    return [
        {
            "id": str(i),
            "headline": headline,
            "summary": "",
            "symbols": [sym],
            "source": source,
            "created_at": (now - timedelta(minutes=i * 18)).isoformat(),
            "url": "",
            "sentiment": sentiment,
        }
        for i, (sym, headline, source, sentiment) in enumerate(headlines)
        if sym in symbols
    ]
