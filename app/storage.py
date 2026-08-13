import json
import os
from datetime import datetime, timezone
from app.config import WATCHLIST_PATH, SCORE_HISTORY_PATH


def _read() -> list[str]:
    if not os.path.exists(WATCHLIST_PATH):
        return []
    with open(WATCHLIST_PATH, "r") as f:
        return json.load(f)


def _write(tickers: list[str]):
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(tickers, f, indent=2)


def get_watchlist() -> list[str]:
    return _read()


def add_to_watchlist(ticker: str) -> list[str]:
    tickers = _read()
    ticker = ticker.upper().strip()
    if ticker not in tickers:
        tickers.append(ticker)
        _write(tickers)
    return tickers


def remove_from_watchlist(ticker: str) -> list[str]:
    tickers = _read()
    ticker = ticker.upper().strip()
    tickers = [t for t in tickers if t != ticker]
    _write(tickers)
    return tickers


def _read_history() -> list[dict]:
    if not os.path.exists(SCORE_HISTORY_PATH):
        return []
    with open(SCORE_HISTORY_PATH, "r") as f:
        return json.load(f)


def get_score_history(ticker: str) -> list[dict]:
    ticker = ticker.upper().strip()
    return [entry for entry in _read_history() if entry["ticker"] == ticker]


def log_score(ticker: str, trade_score: float | None, pillar_scores: dict, financials_sub_scores: dict):
    history = _read_history()
    history.append({
        "ticker": ticker.upper().strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trade_score": trade_score,
        "pillar_scores": pillar_scores,
        "financials_sub_scores": financials_sub_scores,
    })
    with open(SCORE_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)
