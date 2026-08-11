"""
Pulls fundamental + price data for a ticker via yfinance.
Wraps everything in a plain dict so the rest of the app never touches
yfinance's slightly unpredictable Ticker.info schema directly.
"""
import time
import yfinance as yf

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 15 * 60  # yfinance rate-limits aggressively; cache for 15 min


def _get_cached(ticker: str):
    entry = _CACHE.get(ticker)
    if not entry:
        return None
    ts, data = entry
    if time.time() - ts > _CACHE_TTL_SECONDS:
        return None
    return data


def fetch_company_data(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    cached = _get_cached(ticker)
    if cached is not None:
        return cached

    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception as e:
        raise ValueError(
            f"Couldn't fetch data for '{ticker}' from Yahoo Finance ({e}). "
            "This is usually transient rate-limiting - wait a few seconds and retry."
        )

    if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
        raise ValueError(f"No data found for ticker '{ticker}'. Check the symbol is correct.")

    # 200-day moving average for momentum signal
    try:
        hist = t.history(period="1y")
    except Exception:
        hist = None
    if hist is None:
        import pandas as pd
        hist = pd.DataFrame()
    ma_200 = None
    pct_above_ma200 = None
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not hist.empty and len(hist) >= 50:
        ma_200 = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else float(hist["Close"].mean())
        if price and ma_200:
            pct_above_ma200 = round(((price - ma_200) / ma_200) * 100, 2)

    price_52w_high = info.get("fiftyTwoWeekHigh")
    price_52w_low = info.get("fiftyTwoWeekLow")

    data = {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "price": price,
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "peg_ratio": info.get("trailingPegRatio") or info.get("pegRatio"),
        "price_to_book": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "profit_margin": info.get("profitMargins"),
        "operating_margin": info.get("operatingMargins"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "52w_high": price_52w_high,
        "52w_low": price_52w_low,
        "pct_from_52w_high": (
            round(((price - price_52w_high) / price_52w_high) * 100, 2)
            if price and price_52w_high else None
        ),
        "pct_above_200d_ma": pct_above_ma200,
        "analyst_target_price": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationKey"),
    }

    _CACHE[ticker] = (time.time(), data)
    return data
