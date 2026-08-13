"""
Pulls recent StockTwits messages for a ticker via the public, unauthenticated
streams API (~200 req/hour) and scores sentiment. Messages that already carry
a Bullish/Bearish tag use that directly; untagged messages are batch-classified
by Claude in a single call to stay credit-efficient.
This pillar is noisy/contrarian at extremes by nature - kept deliberately simple.
"""
import time
import json
import requests
from anthropic import Anthropic
from app.config import ANTHROPIC_API_KEY

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 15 * 60

_STREAM_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}
MAX_UNTAGGED_TO_CLASSIFY = 20

_client = None

SYSTEM_PROMPT = """You are a markets sentiment classifier for StockTwits posts. You are
given a numbered list of short posts about a stock. For each one, decide if it reads as
bullish, bearish, or neutral. These posts are casual/informal - judge tone and intent, not
just keywords.

Respond ONLY with valid JSON, no markdown fences, matching this schema:
{"items": [{"index": 0, "sentiment": "bullish|bearish|neutral"}]}
One entry per post, in the same order, "index" matching the number given."""


def _get_client():
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file to use /api/social."
            )
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _get_cached(ticker: str):
    entry = _CACHE.get(ticker)
    if not entry:
        return None
    ts, data = entry
    if time.time() - ts > _CACHE_TTL_SECONDS:
        return None
    return data


def _fetch_messages(ticker: str) -> list[dict]:
    try:
        resp = requests.get(_STREAM_URL.format(ticker=ticker), headers=_HEADERS, timeout=15)
    except requests.RequestException as e:
        raise ValueError(f"Couldn't fetch StockTwits data for '{ticker}' ({e}).")

    if resp.status_code == 404:
        raise ValueError(f"No StockTwits stream found for ticker '{ticker}'.")
    if not resp.ok:
        raise ValueError(
            f"StockTwits returned {resp.status_code} for '{ticker}'. "
            "This is usually rate-limiting - wait a bit and retry."
        )

    return resp.json().get("messages", [])


_SENTIMENT_POINTS = {"bullish": 100, "neutral": 50, "bearish": 0}


def _classify_untagged(bodies: list[str]) -> list[str]:
    """Returns a list of sentiment strings, one per body, in order."""
    if not bodies:
        return []

    client = _get_client()
    numbered = "\n".join(f"{i}. {b}" for i, b in enumerate(bodies))
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Posts:\n{numbered}"}],
    )
    raw_text = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    try:
        items = json.loads(raw_text).get("items", [])
    except json.JSONDecodeError:
        items = []

    by_index = {item.get("index"): item.get("sentiment", "neutral") for item in items}
    return [by_index.get(i, "neutral") for i in range(len(bodies))]


def get_social_sentiment(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    cached = _get_cached(ticker)
    if cached is not None:
        return cached

    messages = _fetch_messages(ticker)
    mention_volume = len(messages)

    if not messages:
        result = {"ticker": ticker, "social_score": None, "mention_volume": 0, "items": []}
        _CACHE[ticker] = (time.time(), result)
        return result

    tagged = []
    untagged = []
    for m in messages:
        sentiment = (m.get("entities", {}).get("sentiment") or {}).get("basic")
        body = m.get("body", "")
        if sentiment:
            tagged.append({"body": body, "sentiment": sentiment.lower(), "source": "stocktwits_tag"})
        else:
            untagged.append(body)

    untagged = untagged[:MAX_UNTAGGED_TO_CLASSIFY]
    classified_sentiments = _classify_untagged(untagged)
    classified = [
        {"body": body, "sentiment": sentiment, "source": "claude"}
        for body, sentiment in zip(untagged, classified_sentiments)
    ]

    items = tagged + classified
    points = [_SENTIMENT_POINTS.get(item["sentiment"], 50) for item in items]
    social_score = round(sum(points) / len(points), 1) if points else None

    result = {
        "ticker": ticker,
        "social_score": social_score,
        "mention_volume": mention_volume,
        "items": items,
    }
    _CACHE[ticker] = (time.time(), result)
    return result
