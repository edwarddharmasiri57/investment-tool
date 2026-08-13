"""
Market-wide regime classification: VIX level + 10yr-2yr treasury yield
spread, via simple hardcoded thresholds - no HMM/ML. Free daily macro data
can't support fitting a real regime-switching model reliably, and this
project has no institutional data feed to validate one against. This is a
coarse, rule-based flag meant as CONTEXT for the blend (see blend_service.py),
not a timing/trading signal on its own.

Two real data-source substitutions, both flagged in every response:

1. Originally spec'd to pull the 10y-2y spread from FRED (the standard
   source - DGS10/DGS2 or the T10Y2Y series directly). FRED's keyed API AND
   its keyless CSV download endpoint (fred.stlouisfed.org/graph/fredgraph.csv)
   were both unreachable from this environment at build time - confirmed via
   a direct connectivity test (root domain itself timed out, so this is a
   network-level block, not a code bug). Fell back to yfinance-only tickers.

2. Yahoo Finance has no direct 2yr Treasury constant-maturity yield index
   ticker (^UST2Y / ^US2Y don't exist). Used "2YY=F" (2-Year Treasury Yield
   FUTURES) as a proxy instead - futures yields can diverge from the cash/
   constant-maturity yield FRED would give you, especially around rate-move
   expectations, so the spread here is directionally indicative, not precise.
"""
import time
import yfinance as yf

_CACHE: tuple[float, dict] | None = None
_CACHE_TTL_SECONDS = 15 * 60

VIX_ELEVATED_THRESHOLD = 25
VIX_HIGH_THRESHOLD = 35
INVERSION_THRESHOLD = 0.0  # 10y-2y spread below this = inverted curve, classic recession-risk signal


def _latest_close(ticker: str) -> float | None:
    try:
        hist = yf.Ticker(ticker).history(period="5d")
    except Exception:
        return None
    if hist.empty:
        return None
    return float(hist["Close"].iloc[-1])


def get_market_regime() -> dict:
    global _CACHE
    if _CACHE is not None:
        ts, cached = _CACHE
        if time.time() - ts <= _CACHE_TTL_SECONDS:
            return cached

    vix = _latest_close("^VIX")
    ten_year = _latest_close("^TNX")
    two_year_proxy = _latest_close("2YY=F")

    spread = round(ten_year - two_year_proxy, 3) if ten_year is not None and two_year_proxy is not None else None

    # Volatility takes priority over the curve signal - realized VIX is a faster
    # and more reliable free signal than a futures-based yield-curve proxy.
    if vix is not None and vix >= VIX_HIGH_THRESHOLD:
        regime = "Elevated-Volatility"
        reason = f"VIX at {vix:.1f} is in high-volatility territory (>= {VIX_HIGH_THRESHOLD})."
    elif vix is not None and vix >= VIX_ELEVATED_THRESHOLD:
        regime = "Elevated-Volatility"
        reason = f"VIX at {vix:.1f} is elevated (>= {VIX_ELEVATED_THRESHOLD})."
    elif spread is not None and spread < INVERSION_THRESHOLD:
        regime = "Risk-Off"
        reason = f"10y-2y spread is inverted ({spread:+.2f}pp) - a classic recession-risk signal."
    elif vix is not None:
        regime = "Risk-On"
        reason = f"VIX at {vix:.1f} is calm and the yield curve isn't inverted."
    else:
        regime = "Unknown"
        reason = "Insufficient data (VIX unavailable) to classify."

    result = {
        "regime": regime,
        "reason": reason,
        "vix": round(vix, 2) if vix is not None else None,
        "ten_year_yield_pct": round(ten_year, 3) if ten_year is not None else None,
        "two_year_yield_proxy_pct": round(two_year_proxy, 3) if two_year_proxy is not None else None,
        "ten_minus_two_spread_pp": spread,
        "limitations": [
            "Simple hardcoded thresholds (VIX >=25 elevated / >=35 high; inverted 10y-2y curve = Risk-Off), "
            "not a fitted regime-switching model - free daily macro data can't support fitting one reliably.",
            "FRED (the standard source for the 10y-2y treasury spread) was unreachable from this build "
            "environment - fell back to yfinance-only tickers (^TNX for 10yr).",
            "2yr yield is proxied via '2YY=F' (2-Year Treasury Yield FUTURES), not a constant-maturity cash "
            "yield series like FRED's DGS2 - treat the spread as directionally indicative, not precise.",
            "This is market-wide context, not a per-ticker signal, and not a timing/trading signal on its own.",
        ],
    }
    _CACHE = (time.time(), result)
    return result
