"""
Simple, transparent scoring engine. Every sub-score is 0-100.
Nothing here is a secret sauce - it's readable so you can see exactly
why a company scored the way it did and tune the weights yourself.
"""

DEFAULT_WEIGHTS = {"value": 0.3, "quality": 0.3, "momentum": 0.2, "growth": 0.2}
TRADE_SCORE_WEIGHTS = {"financials": 0.5, "news": 0.3, "social": 0.2}

# Extended weights used only when score_company() is called with dcf/risk data
# (see docstring on score_company). Rebalanced from DEFAULT_WEIGHTS so the four
# original factors still dominate but intrinsic value gets real weight, per the
# "DCF margin of safety is a more serious signal than the composite" argument.
EXTENDED_WEIGHTS = {
    "value": 0.20, "quality": 0.20, "momentum": 0.10, "growth": 0.15,
    "intrinsic_value": 0.25, "financial_strength": 0.10,
}
DISTRESS_PENALTY = 0.5   # Altman Z-Score "distress" zone: composite cut in half
GREY_ZONE_PENALTY = 0.85  # Altman Z-Score "grey" zone: composite cut 15%


def _clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def _score_lower_is_better(value, good, bad):
    """e.g. P/E of `good` or below -> 100, `bad` or above -> 0, linear between."""
    if value is None:
        return None
    if value <= good:
        return 100
    if value >= bad:
        return 0
    return _clamp(100 * (bad - value) / (bad - good))


def _score_higher_is_better(value, bad, good):
    if value is None:
        return None
    if value >= good:
        return 100
    if value <= bad:
        return 0
    return _clamp(100 * (value - bad) / (good - bad))


def score_company(data: dict, dcf: dict | None = None, risk: dict | None = None) -> dict:
    """dcf/risk are optional - pass the dicts returned by dcf_service.get_dcf()
    and risk_service.get_risk_profile() to fold DCF margin of safety and the
    Piotroski F-Score into the composite, and apply an Altman Z-Score distress
    penalty on top. Callers that don't pass them (e.g. /api/company, /api/screen)
    get the exact same plain 4-factor composite as before - this is opt-in so
    the light endpoints don't pay for DCF/statement fetches they don't need.
    """
    # --- Value: cheaper relative to earnings/book = higher score ---
    pe_score = _score_lower_is_better(data.get("pe_ratio"), good=10, bad=40)
    peg_score = _score_lower_is_better(data.get("peg_ratio"), good=1, bad=3)
    pb_score = _score_lower_is_better(data.get("price_to_book"), good=1, bad=8)
    value_parts = [s for s in [pe_score, peg_score, pb_score] if s is not None]
    value_score = round(sum(value_parts) / len(value_parts), 1) if value_parts else None

    # --- Quality: profitability & balance sheet strength ---
    roe = data.get("roe")
    roe_pct = roe * 100 if roe is not None else None
    roe_score = _score_higher_is_better(roe_pct, bad=0, good=25)
    margin = data.get("operating_margin")
    margin_pct = margin * 100 if margin is not None else None
    margin_score = _score_higher_is_better(margin_pct, bad=0, good=25)
    dte_score = _score_lower_is_better(data.get("debt_to_equity"), good=30, bad=200)
    quality_parts = [s for s in [roe_score, margin_score, dte_score] if s is not None]
    quality_score = round(sum(quality_parts) / len(quality_parts), 1) if quality_parts else None

    # --- Momentum: price trend & distance from highs ---
    ma_score = _score_higher_is_better(data.get("pct_above_200d_ma"), bad=-20, good=20)
    from_high = data.get("pct_from_52w_high")
    high_score = _score_higher_is_better(from_high, bad=-40, good=0) if from_high is not None else None
    momentum_parts = [s for s in [ma_score, high_score] if s is not None]
    momentum_score = round(sum(momentum_parts) / len(momentum_parts), 1) if momentum_parts else None

    # --- Growth: revenue & earnings growth ---
    rev_growth = data.get("revenue_growth")
    rev_growth_pct = rev_growth * 100 if rev_growth is not None else None
    rev_score = _score_higher_is_better(rev_growth_pct, bad=-10, good=30)
    earn_growth = data.get("earnings_growth")
    earn_growth_pct = earn_growth * 100 if earn_growth is not None else None
    earn_score = _score_higher_is_better(earn_growth_pct, bad=-10, good=30)
    growth_parts = [s for s in [rev_score, earn_score] if s is not None]
    growth_score = round(sum(growth_parts) / len(growth_parts), 1) if growth_parts else None

    sub_scores = {
        "value": value_score,
        "quality": quality_score,
        "momentum": momentum_score,
        "growth": growth_score,
    }

    extended = dcf is not None or risk is not None
    if extended:
        # --- Intrinsic value: DCF margin of safety, -50% or worse -> 0, +50% or better -> 100 ---
        margin_of_safety = dcf.get("margin_of_safety_pct") if dcf else None
        sub_scores["intrinsic_value"] = _score_higher_is_better(margin_of_safety, bad=-50, good=50)

        # --- Financial strength: Piotroski F-Score (0-9) scaled to 0-100 ---
        f_score = (risk or {}).get("piotroski_f_score", {}).get("f_score")
        sub_scores["financial_strength"] = _clamp(f_score / 9 * 100) if f_score is not None else None

    weights = EXTENDED_WEIGHTS if extended else DEFAULT_WEIGHTS
    available = {k: v for k, v in sub_scores.items() if v is not None}
    if available:
        weight_sum = sum(weights[k] for k in available)
        composite = round(sum(v * weights[k] for k, v in available.items()) / weight_sum, 1)
    else:
        composite = None

    # Altman Z-Score distress override: applied regardless of how good the
    # other factors look, since a bankruptcy-risk flag isn't just "one more
    # factor to average in" - it's a reason to distrust the rest of the score.
    distress_penalty = None
    risk_flag = None
    zone = (risk or {}).get("altman_z_score", {}).get("zone") if risk else None
    if zone == "distress":
        distress_penalty = DISTRESS_PENALTY
        risk_flag = "Altman Z-Score indicates bankruptcy distress risk - composite cut 50% regardless of other factors."
    elif zone == "grey":
        distress_penalty = GREY_ZONE_PENALTY
        risk_flag = "Altman Z-Score is in the grey zone - composite cut 15% as a caution."

    if composite is not None and distress_penalty is not None:
        composite = round(composite * distress_penalty, 1)

    total_factors = len(weights)
    return {
        "composite_score": composite,
        "sub_scores": sub_scores,
        "data_completeness": f"{len(available)}/{total_factors} factors available",
        "distress_penalty_applied": distress_penalty,
        "risk_flag": risk_flag,
    }


def combine_scores(financials_score, news_score, social_score) -> dict:
    """Weighted combine of the financials/news/social pillar composites.
    Missing pillars are dropped and the remaining weights renormalized,
    same approach as score_company()'s sub-score combine.
    """
    pillar_scores = {"financials": financials_score, "news": news_score, "social": social_score}
    available = {k: v for k, v in pillar_scores.items() if v is not None}

    if available:
        weight_sum = sum(TRADE_SCORE_WEIGHTS[k] for k in available)
        composite = round(sum(v * TRADE_SCORE_WEIGHTS[k] for k, v in available.items()) / weight_sum, 1)
    else:
        composite = None

    return {
        "trade_score": composite,
        "pillar_scores": pillar_scores,
        "weights": TRADE_SCORE_WEIGHTS,
        "data_completeness": f"{len(available)}/3 pillars available",
    }
