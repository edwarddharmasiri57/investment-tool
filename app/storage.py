import json
import os
from app.config import WATCHLIST_PATH


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
