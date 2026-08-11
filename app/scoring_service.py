"""
Simple, transparent scoring engine. Every sub-score is 0-100.
Nothing here is a secret sauce - it's readable so you can see exactly
why a company scored the way it did and tune the weights yourself.
"""

DEFAULT_WEIGHTS = {"value": 0.3, "quality": 0.3, "momentum": 0.2, "growth": 0.2}


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


def score_company(data: dict) -> dict:
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

    available = {k: v for k, v in sub_scores.items() if v is not None}
    if available:
        weight_sum = sum(DEFAULT_WEIGHTS[k] for k in available)
        composite = round(sum(v * DEFAULT_WEIGHTS[k] for k, v in available.items()) / weight_sum, 1)
    else:
        composite = None

    return {
        "composite_score": composite,
        "sub_scores": sub_scores,
        "data_completeness": f"{len(available)}/4 factors available",
    }
