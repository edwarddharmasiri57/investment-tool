"""
Simplified single-stage-then-perpetuity discounted cash flow model.

This is a fast intrinsic-value sanity check, not a substitute for a full
analyst model - real DCFs involve segment-level projections, working-capital
detail, a true tax-effected FCFF build, and multi-stage growth fading. Every
response carries an "assumptions" block spelling out exactly what was
hardcoded/simplified (flat WACC, single growth rate, one perpetuity rate)
so the caller can judge how much to trust the number, not just a headline
figure implying more precision than it has.

Notable simplification flagged explicitly: "WACC" here is actually CAPM
cost of EQUITY (risk_free_rate + beta * equity_risk_premium), not a true
weighted-average of cost of equity and after-tax cost of debt. A real WACC
would pull the actual cost of debt and capital-structure weights; this proxy
is directionally reasonable for large, low-distress companies but overstates
the discount rate (and understates intrinsic value) for heavily-levered ones.
"""
import yfinance as yf

from app.config import RISK_FREE_RATE, EQUITY_RISK_PREMIUM
from app.capm_service import get_capm

TERMINAL_GROWTH_RATE = 0.025  # long-run GDP/inflation-ish perpetuity growth, hardcoded
PROJECTION_YEARS = 5
MAX_GROWTH_RATE = 0.15  # cap runaway historical CAGR
MIN_GROWTH_RATE = -0.10  # floor so one bad year doesn't imply permanent collapse
DEFAULT_GROWTH_RATE = 0.03  # fallback when historical CAGR isn't computable


def _historical_fcf_growth_rate(fcf_by_year: list[float]) -> tuple[float, str | None]:
    """fcf_by_year must be oldest->newest. Returns (growth_rate, caveat_note)."""
    usable = fcf_by_year[-4:] if len(fcf_by_year) >= 4 else fcf_by_year
    if len(usable) < 2 or usable[0] <= 0 or usable[-1] <= 0:
        return DEFAULT_GROWTH_RATE, (
            "Historical FCF CAGR wasn't usable (insufficient history, or a negative/zero FCF year) - "
            f"fell back to a flat {DEFAULT_GROWTH_RATE:.0%} growth assumption."
        )
    years = len(usable) - 1
    cagr = (usable[-1] / usable[0]) ** (1 / years) - 1
    capped = max(min(cagr, MAX_GROWTH_RATE), MIN_GROWTH_RATE)
    note = None
    if abs(capped - cagr) > 1e-9:
        note = f"Historical {years}yr FCF CAGR was {cagr:.1%}, capped to {capped:.1%} to avoid unrealistic extrapolation."
    return capped, note


def get_dcf(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    t = yf.Ticker(ticker)

    try:
        info = t.info or {}
        cashflow = t.cashflow
        balance = t.balance_sheet
    except Exception as e:
        raise ValueError(f"Couldn't fetch data for '{ticker}' ({e}).")

    if not info or cashflow.empty or balance.empty:
        raise ValueError(f"No data found for ticker '{ticker}'. Check the symbol is correct.")

    if "Free Cash Flow" not in cashflow.index:
        raise ValueError(f"yfinance doesn't expose a Free Cash Flow line for '{ticker}' - can't run a DCF.")

    fcf_cols = sorted(cashflow.columns)  # oldest -> newest
    fcf_by_year = []
    for col in fcf_cols:
        v = cashflow.loc["Free Cash Flow", col]
        if v is not None and v == v:  # not NaN
            fcf_by_year.append(float(v))
    if not fcf_by_year:
        raise ValueError(f"No usable Free Cash Flow history for '{ticker}'.")

    latest_col = fcf_cols[-1]
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    shares_outstanding = info.get("sharesOutstanding")

    # Prefer the regression-based CAPM beta (capm_service.py - transparent, adjustable window)
    # over yfinance's built-in beta figure; fall back to yfinance's if the regression can't run
    # (e.g. insufficient weekly history for a recent IPO), then to a market beta of 1.0.
    beta = None
    beta_source = None
    try:
        beta = get_capm(ticker)["beta"]
        beta_source = "capm_regression"
    except ValueError:
        beta = info.get("beta")
        beta_source = "yfinance_info" if beta is not None else None

    cash = balance.loc["Cash And Cash Equivalents", latest_col] if "Cash And Cash Equivalents" in balance.index else None
    total_debt = balance.loc["Total Debt", latest_col] if "Total Debt" in balance.index else None

    if not price or not shares_outstanding:
        raise ValueError(f"Missing price or shares outstanding for '{ticker}' - can't compute per-share value.")

    assumptions = {
        "risk_free_rate": RISK_FREE_RATE,
        "equity_risk_premium": EQUITY_RISK_PREMIUM,
        "terminal_growth_rate": TERMINAL_GROWTH_RATE,
        "projection_years": PROJECTION_YEARS,
        "beta_used": beta if beta is not None else 1.0,
        "beta_source": beta_source or "default_market_beta",
    }
    limitations = [
        "\"WACC\" here is CAPM cost of equity (risk_free_rate + beta * equity_risk_premium), not a true "
        "debt/equity-weighted WACC - see module docstring. Understates the discount rate for heavily-levered companies.",
        "Single growth rate applied flatly across all 5 projection years, then a hard jump to terminal growth - "
        "no fade/multi-stage transition, which real models usually include.",
        f"risk_free_rate ({RISK_FREE_RATE:.1%}) and equity_risk_premium ({EQUITY_RISK_PREMIUM:.1%}) are hardcoded "
        "constants, not pulled live - revisit periodically as rates move.",
    ]

    if beta is None:
        assumptions["beta_used"] = 1.0
        limitations.append(
            f"'{ticker}' has no usable beta - neither the CAPM regression (capm_service.py) nor yfinance's "
            "built-in figure was available - assumed market beta of 1.0."
        )
    elif beta_source == "yfinance_info":
        limitations.append(
            "Beta came from yfinance's built-in figure, not the CAPM regression in capm_service.py (the "
            "regression couldn't run - likely insufficient weekly price history) - see /api/capm/{ticker} "
            "for why, if you want the detail."
        )

    if info.get("sector") in ("Financial Services", "Real Estate"):
        limitations.append(
            f"'{ticker}' is in {info.get('sector')} - a Free-Cash-Flow DCF is a known-bad fit for banks/insurers/"
            "REITs (their \"FCF\" isn't economically comparable to an industrial company's, since capital IS "
            "their inventory). Treat this DCF's output as low-confidence to not-meaningful for this ticker."
        )

    growth_rate, growth_note = _historical_fcf_growth_rate(fcf_by_year)
    if growth_note:
        limitations.append(growth_note)

    wacc = RISK_FREE_RATE + (beta if beta is not None else 1.0) * EQUITY_RISK_PREMIUM

    if wacc <= TERMINAL_GROWTH_RATE + 0.005:
        raise ValueError(
            f"Computed discount rate ({wacc:.1%}) is too close to or below the terminal growth rate "
            f"({TERMINAL_GROWTH_RATE:.1%}) for '{ticker}' - the Gordon Growth terminal value formula "
            "isn't valid here (this usually means an unusually low beta). Can't compute a DCF."
        )

    last_fcf = fcf_by_year[-1]
    projected_fcf = [last_fcf * ((1 + growth_rate) ** y) for y in range(1, PROJECTION_YEARS + 1)]
    pv_fcf = [cf / ((1 + wacc) ** y) for y, cf in enumerate(projected_fcf, start=1)]

    terminal_value = projected_fcf[-1] * (1 + TERMINAL_GROWTH_RATE) / (wacc - TERMINAL_GROWTH_RATE)
    pv_terminal_value = terminal_value / ((1 + wacc) ** PROJECTION_YEARS)

    enterprise_value = sum(pv_fcf) + pv_terminal_value
    net_debt = (total_debt or 0) - (cash or 0)
    equity_value = enterprise_value - net_debt
    intrinsic_value_per_share = equity_value / shares_outstanding
    margin_of_safety_pct = round(((intrinsic_value_per_share - price) / price) * 100, 2)

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "intrinsic_value_per_share": round(intrinsic_value_per_share, 2),
        "margin_of_safety_pct": margin_of_safety_pct,
        "wacc": round(wacc, 4),
        "growth_rate_used": round(growth_rate, 4),
        "terminal_growth_rate": TERMINAL_GROWTH_RATE,
        "enterprise_value": round(enterprise_value, 0),
        "equity_value": round(equity_value, 0),
        "net_debt": round(net_debt, 0),
        "projected_fcf": [round(v, 0) for v in projected_fcf],
        "terminal_value": round(terminal_value, 0),
        "historical_fcf": [round(v, 0) for v in fcf_by_year],
        "assumptions": assumptions,
        "limitations": limitations,
    }
