"""
Uses the Anthropic API (with the web search tool) to turn raw fundamentals
into a structured, sourced research note. This is qualitative synthesis to
speed up your own research - it is not a recommendation.
"""
import json
from anthropic import Anthropic
from app.config import ANTHROPIC_API_KEY

_client = None


def _get_client():
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file to use /api/research."
            )
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You are a buy-side equity research assistant. You are given a ticker
and its current fundamentals. Use web search to find recent (last few months) news,
earnings commentary, and competitive developments. Then produce a concise, evidence-led
research note. Be specific and cite what you found - no generic filler, no hype language,
no "exciting opportunity" style copy. Flag real risks as clearly as upside.

Respond ONLY with valid JSON, no markdown fences, matching this schema:
{
  "summary": "2-3 sentence plain-English summary of the current situation",
  "thesis_points": ["specific bullish points grounded in what you found"],
  "risk_points": ["specific bearish/risk points grounded in what you found"],
  "recent_catalysts": ["specific recent news/events with rough dates"],
  "questions_to_investigate": ["follow-up questions worth researching further"]
}"""


def generate_research_note(ticker: str, fundamentals: dict) -> dict:
    client = _get_client()

    user_prompt = f"""Ticker: {ticker}
Company: {fundamentals.get('name')}
Sector: {fundamentals.get('sector')} / {fundamentals.get('industry')}
Current fundamentals: {json.dumps({k: v for k, v in fundamentals.items() if k not in ['ticker', 'name']}, default=str)}

Research this company and produce the structured note."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
    )

    # Concatenate all text blocks (there can be several interleaved with tool use)
    text_parts = [block.text for block in response.content if block.type == "text"]
    raw_text = "\n".join(text_parts).strip()

    # Strip stray markdown fences if the model adds them despite instructions
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    try:
        note = json.loads(raw_text)
    except json.JSONDecodeError:
        note = {"summary": raw_text, "thesis_points": [], "risk_points": [],
                "recent_catalysts": [], "questions_to_investigate": []}

    # Surface which sources were actually used, for transparency
    sources = []
    for block in response.content:
        if block.type == "web_search_tool_result":
            for item in getattr(block, "content", []) or []:
                url = getattr(item, "url", None)
                title = getattr(item, "title", None)
                if url:
                    sources.append({"title": title, "url": url})

    note["sources"] = sources
    return note
