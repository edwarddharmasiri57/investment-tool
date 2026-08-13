"""
Pulls recent headlines for a ticker via yfinance (free, no key) and asks
Claude to classify each one bullish/bearish/neutral with a short reason.
Aggregates into a single 0-100 news_score.
"""
import json
import yfinance as yf
from anthropic import Anthropic
from app.config import ANTHROPIC_API_KEY

_client = None

MAX_HEADLINES = 10

SYSTEM_PROMPT = """You are a markets news classifier. You are given a numbered list of
recent headlines (with short summaries) for a stock ticker. For each one, decide if it
reads as bullish, bearish, or neutral for the stock, and give a one-line reason grounded
in the headline text - no speculation beyond what's stated.

Respond ONLY with valid JSON, no markdown fences, matching this schema:
{"items": [{"index": 0, "sentiment": "bullish|bearish|neutral", "reason": "one line"}]}
One entry per headline, in the same order, "index" matching the number given."""


def _get_client():
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file to use /api/news."
            )
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _fetch_headlines(ticker: str) -> list[dict]:
    t = yf.Ticker(ticker)
    try:
        raw_news = t.news or []
    except Exception as e:
        raise ValueError(f"Couldn't fetch news for '{ticker}' from Yahoo Finance ({e}).")

    headlines = []
    for item in raw_news[:MAX_HEADLINES]:
        content = item.get("content", {})
        title = content.get("title")
        if not title:
            continue
        headlines.append({
            "title": title,
            "summary": content.get("summary") or "",
            "publisher": (content.get("provider") or {}).get("displayName"),
            "published": content.get("pubDate"),
            "url": (content.get("canonicalUrl") or {}).get("url"),
        })
    return headlines


def _classify(headlines: list[dict]) -> list[dict]:
    client = _get_client()
    numbered = "\n".join(
        f"{i}. {h['title']} - {h['summary']}" for i, h in enumerate(headlines)
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Headlines:\n{numbered}"}],
    )
    raw_text = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    try:
        parsed = json.loads(raw_text)
        items = parsed.get("items", [])
    except json.JSONDecodeError:
        items = []

    by_index = {item.get("index"): item for item in items}
    results = []
    for i, h in enumerate(headlines):
        classification = by_index.get(i, {"sentiment": "neutral", "reason": "Not classified."})
        results.append({
            "headline": h["title"],
            "publisher": h["publisher"],
            "published": h["published"],
            "url": h["url"],
            "sentiment": classification.get("sentiment", "neutral"),
            "reason": classification.get("reason", ""),
        })
    return results


_SENTIMENT_POINTS = {"bullish": 100, "neutral": 50, "bearish": 0}


def _score(classified: list[dict]) -> float | None:
    if not classified:
        return None
    points = [_SENTIMENT_POINTS.get(c["sentiment"], 50) for c in classified]
    return round(sum(points) / len(points), 1)


def get_news_sentiment(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    headlines = _fetch_headlines(ticker)
    if not headlines:
        return {"ticker": ticker, "news_score": None, "items": []}

    classified = _classify(headlines)
    return {
        "ticker": ticker,
        "news_score": _score(classified),
        "items": classified,
    }
