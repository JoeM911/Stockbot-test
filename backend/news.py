from typing import List
import httpx


POSITIVE_WORDS = {"surge", "rally", "beat", "gain", "up", "rise", "profit", "bullish", "growth", "record", "strong"}
NEGATIVE_WORDS = {"drop", "fall", "miss", "loss", "down", "decline", "bearish", "crash", "weak", "cut", "layoff"}


def estimate_sentiment(text: str) -> str:
    words = set(text.lower().split())
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


async def fetch_news(api_key: str, secret_key: str, symbols: List[str]) -> List[dict]:
    if not api_key or not secret_key:
        return []
    try:
        headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        }
        params = {"symbols": ",".join(symbols), "limit": 30, "sort": "desc"}
        url = "https://data.alpaca.markets/v1beta1/news"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        return [
            {
                "id": str(a.get("id", "")),
                "headline": a.get("headline", ""),
                "summary": a.get("summary", ""),
                "symbols": a.get("symbols", []),
                "source": a.get("source", ""),
                "created_at": a.get("created_at", ""),
                "url": a.get("url", ""),
                "sentiment": estimate_sentiment(a.get("headline", "")),
            }
            for a in data.get("news", [])
        ]
    except Exception as e:
        print(f"News fetch error: {e}")
        return []
