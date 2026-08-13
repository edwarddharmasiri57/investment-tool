"""
CAPM beta (regression-based - more transparent/adjustable than yfinance's
built-in `beta` figure, which uses an opaque window/methodology) and CAPM
expected return. Standard textbook/CFA-curriculum methodology (Sharpe 1964 /
Lintner 1965): single-factor OLS of weekly stock returns against S&P 500
(^GSPC) returns over a rolling window.

This beta feeds into dcf_service.py's WACC calculation, replacing yfinance's
built-in beta there (with a fallback to it if this regression can't run -
see dcf_service.py's beta-selection logic).
"""
import numpy as np
import pandas as pd
import yfinance as yf

from app.config import RISK_FREE_RATE, EQUITY_RISK_PREMIUM

MARKET_TICKER = "^GSPC"
DEFAULT_WINDOW_YEARS = 3
MIN_WEEKS_FOR_REGRESSION = 52  # ~1 year minimum

METHODOLOGY = "CAPM (Sharpe 1964 / Lintner 1965), OLS regression of weekly stock returns vs S&P 500 (^GSPC) returns."


def get_capm(ticker: str, years: int = DEFAULT_WINDOW_YEARS) -> dict:
    ticker = ticker.upper().strip()
    try:
        stock_hist = yf.Ticker(ticker).history(period=f"{years}y", interval="1wk")
        market_hist = yf.Ticker(MARKET_TICKER).history(period=f"{years}y", interval="1wk")
    except Exception as e:
        raise ValueError(f"Couldn't fetch price history for '{ticker}' or the market ({e}).")

    if stock_hist.empty or market_hist.empty:
        raise ValueError(f"No price history available for '{ticker}' or the market index.")

    stock_returns = stock_hist["Close"].pct_change().dropna()
    market_returns = market_hist["Close"].pct_change().dropna()

    # pandas aligns the two Series by index (date) automatically; dropna keeps only
    # weeks where both have a value, handling any minor date-alignment mismatches.
    aligned = pd.DataFrame({"stock": stock_returns, "market": market_returns}).dropna()

    if len(aligned) < MIN_WEEKS_FOR_REGRESSION:
        raise ValueError(
            f"Only {len(aligned)} overlapping weekly data points for '{ticker}' vs the market - "
            f"need >= {MIN_WEEKS_FOR_REGRESSION} for a meaningful regression."
        )

    y = aligned["stock"].values
    X = np.column_stack([np.ones(len(aligned)), aligned["market"].values])
    coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    alpha, beta = coeffs

    y_pred = X @ coeffs
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else None

    expected_return = RISK_FREE_RATE + beta * EQUITY_RISK_PREMIUM

    return {
        "ticker": ticker,
        "methodology": METHODOLOGY,
        "market_ticker": MARKET_TICKER,
        "window_years": years,
        "weeks_used": len(aligned),
        "beta": round(float(beta), 4),
        "alpha_weekly_pct": round(float(alpha) * 100, 4),
        "r_squared": round(float(r_squared), 4) if r_squared is not None else None,
        "risk_free_rate": RISK_FREE_RATE,
        "equity_risk_premium": EQUITY_RISK_PREMIUM,
        "capm_expected_return_pct": round(expected_return * 100, 2),
        "limitations": [
            "Regression-based beta over a rolling window - will differ from yfinance's own trailing beta "
            "figure (different window/frequency/methodology) and from Bloomberg-style adjusted beta.",
            "No p-values/standard errors computed - alpha/beta are point estimates only, not tested for "
            "statistical significance.",
            f"risk_free_rate ({RISK_FREE_RATE:.1%}) and equity_risk_premium ({EQUITY_RISK_PREMIUM:.1%}) are "
            "hardcoded constants shared with dcf_service.py - not pulled live.",
            "Beta is known to be unstable/time-varying for individual stocks - a 3yr weekly window is a "
            "common choice but just one of many reasonable windows; results can shift with window length.",
        ],
    }
