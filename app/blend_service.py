"""
Blends existing signals as separate "views" with fixed confidence weights.

This is deliberately NOT a proper Black-Litterman model - that needs a full
covariance matrix across a real universe (to know how views correlate and to
combine them with a market-implied equilibrium prior), which this project has
no data source for. This is a transparent weighted average instead: each
view's raw score, weight, and dollar-for-dollar contribution to the blend is
shown in `breakdown`, so it's auditable rather than a black box.
"""
from app.data_service import fetch_company_data
from app.scoring_service import score_company
from app.dcf_service import get_dcf
from app.news_service import get_news_sentiment
from app.social_service import get_social_sentiment
from app.regime_service import get_market_regime

# (weight, confidence label, rationale) - fixed, hand-set constants based on
# qualitative judgment about each signal's reliability, NOT fitted/backtested
# against realized returns. See get_blend()'s "limitations" for the caveats
# an institutional version would need to address before trusting these.
BLEND_WEIGHTS = {
    "fundamentals": (0.45, "high", "Rule-based and deterministic, not subject to short-term noise."),
    "dcf": (0.25, "medium", "Sensitive to WACC/growth assumptions - see dcf_service.py's own limitations."),
    "news": (0.20, "medium-low", "Real signal but short-lived - today's headlines fade fast."),
    "social": (0.10, "low", "Noisy and often contrarian at extremes - see social_service.py."),
}


def get_blend(ticker: str, data: dict | None = None, dcf: dict | None = None) -> dict:
    """data/dcf are optional - pass already-fetched results (e.g. from
    universe_service's scan loop, which needs both anyway) to avoid a
    redundant fetch. dcf_service has no caching of its own, so skipping this
    matters for a 500-ticker batch job, not just as a micro-optimization.
    """
    ticker = ticker.upper().strip()

    if data is None:
        data = fetch_company_data(ticker)  # raises ValueError if ticker not found - let it propagate
    fundamentals_score = score_company(data)["composite_score"]

    if dcf is None:
        try:
            dcf = get_dcf(ticker)
        except ValueError:
            dcf = None
    margin_of_safety = dcf.get("margin_of_safety_pct") if dcf else None
    # Rescale margin of safety onto the same 0-100 scale as the other views
    # (-50% -> 0, +50% -> 100, clamped) - matches scoring_service.py's own
    # intrinsic_value sub-score convention. This rescaling is arbitrary, not
    # derived from any statistical relationship between margin of safety and
    # forward returns - just what's needed to make the views combinable.
    dcf_score = max(0.0, min(100.0, 50 + margin_of_safety)) if margin_of_safety is not None else None

    try:
        news_score = get_news_sentiment(ticker).get("news_score")
    except (ValueError, RuntimeError):
        news_score = None

    try:
        social_score = get_social_sentiment(ticker).get("social_score")
    except (ValueError, RuntimeError):
        social_score = None

    views = {"fundamentals": fundamentals_score, "dcf": dcf_score, "news": news_score, "social": social_score}
    available = {k: v for k, v in views.items() if v is not None}

    breakdown = {}
    blended_score = None
    if available:
        weight_sum = sum(BLEND_WEIGHTS[k][0] for k in available)
        blended_score = round(sum(v * BLEND_WEIGHTS[k][0] for k, v in available.items()) / weight_sum, 1)
        for k, v in available.items():
            normalized_weight = BLEND_WEIGHTS[k][0] / weight_sum
            breakdown[k] = {
                "score": round(v, 1),
                "confidence": BLEND_WEIGHTS[k][1],
                "rationale": BLEND_WEIGHTS[k][2],
                "raw_weight": BLEND_WEIGHTS[k][0],
                "normalized_weight": round(normalized_weight, 3),
                "contribution": round(v * normalized_weight, 1),
            }

    regime = get_market_regime()
    regime_note = None
    if regime["regime"] in ("Risk-Off", "Elevated-Volatility"):
        regime_note = (
            f"Market regime is currently {regime['regime']} ({regime['reason']}) - shown as context only, "
            "the blended score above was NOT adjusted for this, per design."
        )

    return {
        "ticker": ticker,
        "blended_score": blended_score,
        "breakdown": breakdown,
        "views_available": f"{len(available)}/4",
        "market_regime": regime["regime"],
        "regime_note": regime_note,
        "limitations": [
            "This is a transparent weighted average, not a real Black-Litterman model - no covariance matrix, "
            "no market-implied equilibrium prior, and no accounting for correlation between views (e.g. news "
            "and social sentiment often move together, so their combined weight can double-count one underlying "
            "event rather than adding independent information).",
            "Confidence weights (fundamentals .45 / DCF .25 / news .20 / social .10) are fixed, hand-set "
            "constants, not fitted/backtested against realized returns.",
            "DCF's margin_of_safety_pct is linearly rescaled onto the 0-100 scale purely to make it combinable "
            "with the other views - the rescaling itself is arbitrary.",
        ],
    }
