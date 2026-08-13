"""
Comparable company analysis: places a ticker's EV/EBITDA, EV/Revenue, and P/E
against its sector peer group's median, so "P/E of 15" gets judged against
the right yardstick instead of a single global threshold.

Peer groups here come from a small HARDCODED per-sector list of large,
liquid names (see SECTOR_PEERS below), not a full peer-discovery process a
real comps grid would use (closer market-cap bands, same sub-industry, deal
comps, etc). This is a real simplification: a mega-cap and a mid-cap in the
same GICS sector can have structurally different multiples for reasons that
have nothing to do with over/undervaluation. Treat premium/discount % as a
rough signal, not a precise mispricing estimate.
"""
import time
import yfinance as yf

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 15 * 60

SECTOR_PEERS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "ORCL", "CRM", "ADBE"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST", "CL", "MDLZ"],
    "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK"],
    "Industrials": ["HON", "UPS", "CAT", "BA", "GE", "LMT", "RTX"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "PSX"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP"],
    "Real Estate": ["PLD", "AMT", "EQIX", "PSA", "O"],
    "Basic Materials": ["LIN", "SHW", "APD", "ECL", "NEM"],
}
MIN_PEERS_FOR_MEDIAN = 3


def _get_cached_metrics(ticker: str):
    entry = _CACHE.get(ticker)
    if not entry:
        return None
    ts, data = entry
    if time.time() - ts > _CACHE_TTL_SECONDS:
        return None
    return data


def _fetch_metrics(ticker: str) -> dict | None:
    cached = _get_cached_metrics(ticker)
    if cached is not None:
        return cached

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return None

    ev = info.get("enterpriseValue")
    ebitda = info.get("ebitda")
    revenue = info.get("totalRevenue")
    pe = info.get("trailingPE")

    metrics = {
        "sector": info.get("sector"),
        "ev_to_ebitda": (ev / ebitda) if ev and ebitda and ebitda > 0 else None,
        "ev_to_revenue": (ev / revenue) if ev and revenue and revenue > 0 else None,
        "pe_ratio": pe if pe and pe > 0 else None,
    }
    _CACHE[ticker] = (time.time(), metrics)
    return metrics


def _median(values: list[float]) -> float | None:
    vals = sorted(v for v in values if v is not None)
    n = len(vals)
    if n == 0:
        return None
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


def get_comps(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    company_metrics = _fetch_metrics(ticker)
    if company_metrics is None:
        raise ValueError(f"Couldn't fetch data for '{ticker}'. Check the symbol is correct.")

    sector = company_metrics["sector"]
    peer_list = SECTOR_PEERS.get(sector, [])
    peer_tickers = [p for p in peer_list if p != ticker]

    if not peer_tickers:
        raise ValueError(
            f"No hardcoded peer group for sector '{sector}' (ticker '{ticker}') - "
            "SECTOR_PEERS only covers a handful of major sectors."
        )

    peer_metrics = []
    for peer in peer_tickers:
        m = _fetch_metrics(peer)
        if m is not None:
            peer_metrics.append({"ticker": peer, **m})

    def premium_discount(company_val, peer_vals):
        median = _median(peer_vals)
        if company_val is None or median is None or median == 0:
            return median, None
        return median, round(((company_val - median) / median) * 100, 1)

    ev_ebitda_median, ev_ebitda_premium = premium_discount(
        company_metrics["ev_to_ebitda"], [p["ev_to_ebitda"] for p in peer_metrics]
    )
    ev_revenue_median, ev_revenue_premium = premium_discount(
        company_metrics["ev_to_revenue"], [p["ev_to_revenue"] for p in peer_metrics]
    )
    pe_median, pe_premium = premium_discount(
        company_metrics["pe_ratio"], [p["pe_ratio"] for p in peer_metrics]
    )

    usable_peer_count = len([p for p in peer_metrics if p["ev_to_ebitda"] or p["ev_to_revenue"] or p["pe_ratio"]])
    limitations = [
        "Peer group is a small hardcoded list of large/liquid names per sector (see SECTOR_PEERS), not a "
        "full peer-discovery process - market-cap mismatches within the same sector are not controlled for.",
    ]
    if usable_peer_count < MIN_PEERS_FOR_MEDIAN:
        limitations.append(
            f"Only {usable_peer_count} peers had usable data - median is based on a small sample, "
            "treat the premium/discount figures as low-confidence."
        )

    return {
        "ticker": ticker,
        "sector": sector,
        "peers_used": [p["ticker"] for p in peer_metrics],
        "company": {
            "ev_to_ebitda": round(company_metrics["ev_to_ebitda"], 2) if company_metrics["ev_to_ebitda"] else None,
            "ev_to_revenue": round(company_metrics["ev_to_revenue"], 2) if company_metrics["ev_to_revenue"] else None,
            "pe_ratio": round(company_metrics["pe_ratio"], 2) if company_metrics["pe_ratio"] else None,
        },
        "peer_median": {
            "ev_to_ebitda": round(ev_ebitda_median, 2) if ev_ebitda_median else None,
            "ev_to_revenue": round(ev_revenue_median, 2) if ev_revenue_median else None,
            "pe_ratio": round(pe_median, 2) if pe_median else None,
        },
        "premium_discount_pct": {
            "ev_to_ebitda": ev_ebitda_premium,
            "ev_to_revenue": ev_revenue_premium,
            "pe_ratio": pe_premium,
        },
        "limitations": limitations,
    }
