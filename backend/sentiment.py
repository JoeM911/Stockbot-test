"""
Social sentiment analyzer — pulls bullish/bearish signal from StockTwits
(free, no API key) and Reddit r/wallstreetbets ticker mentions.
Results are cached 5 minutes to stay within rate limits.
"""
import asyncio
import re
import time
from typing import Dict, List, Optional

import httpx

_TICKER_RE = re.compile(r'\b\$?([A-Z]{2,5})\b')
_SKIP = {"I", "A", "AT", "BE", "DD", "FOR", "IN", "IS", "IT", "NEW",
         "ON", "OR", "THE", "TO", "UP", "US", "WSB", "THE", "AND", "ARE",
         "BUT", "BUY", "NOT", "NOW", "OUT", "SEC", "SHORT", "YOLO"}


class SentimentAnalyzer:
    def __init__(self):
        self._sym_cache:  Dict[str, dict]  = {}
        self._sym_ts:     Dict[str, float] = {}
        self._trend_cache: List[dict] = []
        self._trend_ts:    float = 0
        self._reddit_cache: List[dict] = []
        self._reddit_ts:    float = 0
        self.TTL = 300  # 5-min cache

    # ---------------------------------------------------------------- public

    async def get_trending(self) -> List[dict]:
        """Top symbols by volume on StockTwits."""
        if time.time() - self._trend_ts < self.TTL:
            return self._trend_cache
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
                r = await c.get(
                    "https://api.stocktwits.com/api/2/trending/symbols.json",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
                )
                print(f"[Sentiment] StockTwits trending status: {r.status_code}")
                data = r.json()
                syms = data.get("symbols", [])
                self._trend_cache = [
                    {"symbol": s["symbol"], "watchlist_count": s.get("watchlist_count", 0)}
                    for s in syms[:20]
                ]
                self._trend_ts = time.time()
        except Exception as e:
            print(f"[Sentiment] trending: {e}")
        return self._trend_cache

    async def get_symbol_sentiment(self, symbol: str) -> Optional[dict]:
        """Bullish/bearish ratio from the last 30 StockTwits messages."""
        if time.time() - self._sym_ts.get(symbol, 0) < self.TTL:
            return self._sym_cache.get(symbol)
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
                r = await c.get(
                    f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
                )
                messages = r.json().get("messages", [])
                bullish = sum(
                    1 for m in messages
                    if (m.get("entities") or {}).get("sentiment", {}) and
                       m["entities"]["sentiment"].get("basic") == "Bullish"
                )
                bearish = sum(
                    1 for m in messages
                    if (m.get("entities") or {}).get("sentiment", {}) and
                       m["entities"]["sentiment"].get("basic") == "Bearish"
                )
                labelled = bullish + bearish
                result = {
                    "symbol": symbol,
                    "bullish": bullish,
                    "bearish": bearish,
                    "total_msgs": len(messages),
                    "bullish_pct": round(bullish / labelled * 100) if labelled else 50,
                    "bearish_pct": round(bearish / labelled * 100) if labelled else 50,
                    "score": round((bullish - bearish) / max(labelled, 1), 3),
                    "source": "stocktwits",
                }
                self._sym_cache[symbol] = result
                self._sym_ts[symbol] = time.time()
                return result
        except Exception as e:
            print(f"[Sentiment] {symbol}: {e}")
            return None

    async def scan_sentiment(self, symbols: List[str]) -> List[dict]:
        """Batch-fetch sentiment for a list of symbols (rate-limit friendly)."""
        results = await asyncio.gather(
            *[self.get_symbol_sentiment(s) for s in symbols],
            return_exceptions=True,
        )
        valid = [r for r in results if isinstance(r, dict)]
        return sorted(valid, key=lambda x: x["score"], reverse=True)

    async def get_reddit_mentions(self) -> List[dict]:
        """Top ticker mentions in r/wallstreetbets (new + hot posts)."""
        if time.time() - self._reddit_ts < self.TTL:
            return self._reddit_cache
        counts: Dict[str, int] = {}
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as c:
                for sort in ("hot", "new"):
                    r = await c.get(
                        f"https://www.reddit.com/r/wallstreetbets/{sort}.json?limit=50&raw_json=1"
                    )
                    print(f"[Sentiment] Reddit WSB {sort} status: {r.status_code}")
                    if r.status_code != 200:
                        print(f"[Sentiment] Reddit response: {r.text[:200]}")
                        continue
                    posts = r.json().get("data", {}).get("children", [])
                    for post in posts:
                        title = post.get("data", {}).get("title", "")
                        score = post.get("data", {}).get("score", 1)
                        for m in _TICKER_RE.finditer(title.upper()):
                            t = m.group(1)
                            if t not in _SKIP and len(t) <= 5:
                                counts[t] = counts.get(t, 0) + max(1, int(score ** 0.5))
        except Exception as e:
            print(f"[Sentiment] reddit: {e}")

        self._reddit_cache = sorted(
            [{"symbol": k, "mentions": v, "source": "reddit/wsb"}
             for k, v in counts.items()],
            key=lambda x: x["mentions"], reverse=True,
        )[:20]
        self._reddit_ts = time.time()
        return self._reddit_cache
