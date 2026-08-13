"""
Mean-Variance Optimization (Markowitz, 1952) and Risk Parity weighting for
the current demo-portfolio holdings, plus a pairwise correlation check.
Both are standard portfolio-theory methodology, computed from historical
daily returns via yfinance - no ML, no institutional data.

Returns MVO's max-Sharpe weights and risk-parity weights ALONGSIDE the
portfolio's actual current weights, purely for comparison - this endpoint
does not rebalance anything.

IMPORTANT CAVEAT, stated explicitly because it's a real, well-known limitation
and not just a formality: Mean-Variance Optimization is highly sensitive to
the historical mean-return estimates used as its input - small changes in
those estimates can swing the "optimal" weights wildly (this is precisely
why risk parity exists as an alternative: it only needs the covariance
matrix, not return estimates, and is far more robust to estimation error).
Treat MVO's output here as directional, not precise.
"""
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize

from app.config import RISK_FREE_RATE
from app.portfolio_service import get_positions

TRADING_DAYS_PER_YEAR = 252
HISTORY_YEARS = 2
MIN_POSITIONS = 2
HIGH_CORRELATION_THRESHOLD = 0.8

METHODOLOGY_MVO = "Mean-Variance Optimization / max-Sharpe efficient frontier point (Markowitz, 1952)."
METHODOLOGY_RISK_PARITY = "Risk Parity (equal risk contribution) weighting - does not require return estimates."


def _fetch_daily_returns(tickers: list[str]) -> pd.DataFrame:
    closes = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period=f"{HISTORY_YEARS}y", interval="1d")
        except Exception:
            continue
        if not hist.empty:
            closes[ticker] = hist["Close"]
    if len(closes) < MIN_POSITIONS:
        raise ValueError("Not enough tickers with usable price history to optimize.")
    prices = pd.DataFrame(closes).dropna()
    return prices.pct_change().dropna()


def _portfolio_vol(weights, cov_matrix):
    return float(np.sqrt(weights @ cov_matrix @ weights))


def _max_sharpe_weights(mean_returns: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
    n = len(mean_returns)

    def neg_sharpe(w):
        ret = w @ mean_returns
        vol = _portfolio_vol(w, cov_matrix)
        return -(ret - RISK_FREE_RATE) / vol if vol > 0 else 0.0

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0.0, 1.0)] * n  # long-only, no leverage - a real simplification vs. an unconstrained MVO
    x0 = np.repeat(1 / n, n)
    result = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    return result.x if result.success else x0


def _risk_parity_weights(cov_matrix: np.ndarray) -> np.ndarray:
    n = cov_matrix.shape[0]

    def risk_parity_objective(w):
        port_vol = _portfolio_vol(w, cov_matrix)
        if port_vol == 0:
            return 0.0
        marginal_contrib = cov_matrix @ w
        risk_contrib = w * marginal_contrib / port_vol
        target = port_vol / n
        return float(np.sum((risk_contrib - target) ** 2))

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(1e-6, 1.0)] * n  # small positive floor avoids a zero-weight singularity in the objective
    x0 = np.repeat(1 / n, n)
    result = minimize(risk_parity_objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    weights = result.x if result.success else x0
    return weights / weights.sum()


def get_portfolio_optimization() -> dict:
    positions = get_positions()
    if len(positions) < MIN_POSITIONS:
        raise ValueError(f"Need at least {MIN_POSITIONS} open positions to optimize - currently {len(positions)}.")

    tickers = [p["ticker"] for p in positions]
    returns = _fetch_daily_returns(tickers)
    usable_tickers = list(returns.columns)
    if len(usable_tickers) < MIN_POSITIONS:
        raise ValueError("Not enough tickers with overlapping price history to optimize.")

    mean_daily = returns[usable_tickers].mean().values
    mean_annual = mean_daily * TRADING_DAYS_PER_YEAR
    cov_daily = returns[usable_tickers].cov().values
    cov_annual = cov_daily * TRADING_DAYS_PER_YEAR

    mvo_weights = _max_sharpe_weights(mean_annual, cov_annual)
    rp_weights = _risk_parity_weights(cov_annual)

    positions_by_ticker = {p["ticker"]: p for p in positions}
    total_value = sum(positions_by_ticker[t]["market_value"] for t in usable_tickers if positions_by_ticker[t]["market_value"])
    current_weights = {
        t: round((positions_by_ticker[t]["market_value"] or 0) / total_value, 4) if total_value else None
        for t in usable_tickers
    }

    corr_matrix = returns[usable_tickers].corr()
    high_correlation_pairs = []
    for i, t1 in enumerate(usable_tickers):
        for t2 in usable_tickers[i + 1:]:
            corr = corr_matrix.loc[t1, t2]
            if corr > HIGH_CORRELATION_THRESHOLD:
                high_correlation_pairs.append({"pair": [t1, t2], "correlation": round(float(corr), 3)})

    mvo_sharpe = None
    mvo_vol = _portfolio_vol(mvo_weights, cov_annual)
    if mvo_vol > 0:
        mvo_sharpe = round(float((mvo_weights @ mean_annual - RISK_FREE_RATE) / mvo_vol), 3)

    return {
        "tickers": usable_tickers,
        "history_years": HISTORY_YEARS,
        "current_weights": current_weights,
        "mvo": {
            "methodology": METHODOLOGY_MVO,
            "weights": {t: round(float(w), 4) for t, w in zip(usable_tickers, mvo_weights)},
            "expected_annual_return_pct": round(float(mvo_weights @ mean_annual) * 100, 2),
            "expected_annual_volatility_pct": round(mvo_vol * 100, 2),
            "sharpe_ratio": mvo_sharpe,
        },
        "risk_parity": {
            "methodology": METHODOLOGY_RISK_PARITY,
            "weights": {t: round(float(w), 4) for t, w in zip(usable_tickers, rp_weights)},
        },
        "correlation_matrix": {t1: {t2: round(float(corr_matrix.loc[t1, t2]), 3) for t2 in usable_tickers} for t1 in usable_tickers},
        "high_correlation_warnings": high_correlation_pairs,
        "limitations": [
            "MVO is highly sensitive to the historical mean-return estimates used as input - small changes in "
            "those estimates can swing the 'optimal' weights wildly. Treat MVO's output as directional, not "
            "precise. Risk parity avoids this specific problem (no return estimates needed) but is not immune "
            "to estimation error in the covariance matrix itself.",
            "Both are long-only, no-leverage optimizations (weights bounded [0,1]) - a real simplification "
            "vs. an unconstrained Markowitz frontier.",
            f"Expected returns/covariance are historical ({HISTORY_YEARS}yr daily, annualized ×252) - "
            "past returns/volatility/correlation are not guaranteed to persist forward.",
            "This compares suggested weights against your actual current weights - nothing here rebalances "
            "the demo portfolio automatically.",
        ],
    }
