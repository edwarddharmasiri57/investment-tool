"""
Real performance measurement of the demo portfolio, computed from its ACTUAL
logged trade history - not a backtest of predictions. There's no look-ahead
risk here: the reconstructed NAV on any given day only reflects trades whose
`date` is on or before that day, so this is a faithful historical
reconstruction of what the account was actually worth, forward-looking from
when each trade was logged.

IMPORTANT: portfolio.json only stores the trade log + current cash, not a
stored day-by-day NAV history. This module reconstructs one by replaying the
trade log chronologically against REAL historical daily closing prices
(yfinance), business day by business day, from the first trade's date
through today.
"""
import numpy as np
import pandas as pd
import yfinance as yf

from app.config import RISK_FREE_RATE
from app.portfolio_service import get_trade_log, get_starting_cash

MARKET_TICKER = "^GSPC"
TRADING_DAYS_PER_YEAR = 252
MIN_DAYS_FOR_MEANINGFUL_METRICS = 20  # ~1 trading month - below this, annualized figures are close to noise


def _reconstruct_nav_history(trades: list[dict], starting_cash: float) -> pd.Series:
    trades_sorted = sorted(trades, key=lambda t: t["date"])
    start_date = trades_sorted[0]["date"]
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")

    tickers = sorted(set(t["ticker"] for t in trades_sorted))
    price_data = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(start=start_date, end=end_date)
        except Exception:
            continue
        if not hist.empty:
            hist.index = hist.index.date
            price_data[ticker] = hist["Close"]

    date_range = pd.bdate_range(start=start_date, end=end_date)
    cash = starting_cash
    holdings: dict[str, float] = {}
    trade_idx = 0
    nav, nav_dates = [], []

    for day in date_range:
        day_date = day.date()
        while trade_idx < len(trades_sorted) and pd.Timestamp(trades_sorted[trade_idx]["date"]).date() <= day_date:
            t = trades_sorted[trade_idx]
            if t["action"] == "BUY":
                cash -= t["quantity"] * t["price"]
                holdings[t["ticker"]] = holdings.get(t["ticker"], 0.0) + t["quantity"]
            else:
                cash += t["quantity"] * t["price"]
                holdings[t["ticker"]] = holdings.get(t["ticker"], 0.0) - t["quantity"]
            trade_idx += 1

        positions_value = 0.0
        for ticker, qty in holdings.items():
            if qty <= 1e-9:
                continue
            series = price_data.get(ticker)
            if series is None:
                continue
            available = series[series.index <= day_date]  # forward-fill from the last known close
            if not available.empty:
                positions_value += qty * float(available.iloc[-1])

        nav.append(cash + positions_value)
        nav_dates.append(day_date)

    return pd.Series(nav, index=pd.DatetimeIndex(nav_dates))


def _max_drawdown(nav: pd.Series) -> float:
    running_max = nav.cummax()
    drawdown = (nav - running_max) / running_max
    return float(drawdown.min())


def get_portfolio_performance() -> dict:
    trades = get_trade_log()
    if not trades:
        raise ValueError("No trades logged yet - nothing to measure.")

    starting_cash = get_starting_cash()
    nav = _reconstruct_nav_history(trades, starting_cash)
    daily_returns = nav.pct_change().dropna()

    days_elapsed = (nav.index[-1] - nav.index[0]).days
    insufficient_history = len(daily_returns) < MIN_DAYS_FOR_MEANINGFUL_METRICS

    years_elapsed = max(days_elapsed / 365.25, 1 / 365.25)
    cagr = (nav.iloc[-1] / starting_cash) ** (1 / years_elapsed) - 1 if nav.iloc[-1] > 0 else None

    daily_rf = RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
    excess_returns = daily_returns - daily_rf
    sharpe = None
    if daily_returns.std() > 0:
        sharpe = float(excess_returns.mean() / daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))

    downside_returns = daily_returns[daily_returns < 0]
    sortino = None
    if len(downside_returns) > 0 and downside_returns.std() > 0:
        sortino = float(excess_returns.mean() / downside_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))

    information_ratio = None
    try:
        benchmark_hist = yf.Ticker(MARKET_TICKER).history(start=nav.index[0].strftime("%Y-%m-%d"), end=pd.Timestamp.now().strftime("%Y-%m-%d"))
        benchmark_hist.index = benchmark_hist.index.date
        benchmark_returns = benchmark_hist["Close"].pct_change().dropna()
        benchmark_returns.index = pd.DatetimeIndex(benchmark_returns.index)
        aligned = pd.DataFrame({"portfolio": daily_returns, "benchmark": benchmark_returns}).dropna()
        active_returns = aligned["portfolio"] - aligned["benchmark"]
        if len(active_returns) > 1 and active_returns.std() > 0:
            information_ratio = float(active_returns.mean() / active_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    except Exception:
        information_ratio = None

    max_dd = _max_drawdown(nav)

    limitations = [
        "Sharpe/Sortino/Information Ratio/CAGR are all ANNUALIZED from the actual elapsed history - with a "
        "short trade history, annualizing amplifies noise enormously (e.g. 8 days of real returns extrapolated "
        "to a 1-year figure is not a meaningful estimate of anything). Check 'days_elapsed' and "
        "'insufficient_history' before trusting these numbers.",
        "Sortino uses 0% as the Minimum Acceptable Return (downside deviation = std of days with negative "
        "return) - a common simplification; some definitions use the risk-free rate as the MAR instead.",
        "NAV history is RECONSTRUCTED from the trade log against real historical closes (forward-filled on "
        "non-trading days per ticker), not a stored snapshot log - see module docstring.",
        f"risk_free_rate ({RISK_FREE_RATE:.1%}) is the same hardcoded constant used elsewhere in this project.",
    ]
    if insufficient_history:
        limitations.insert(0, (
            f"Only {len(daily_returns)} daily return observations ({days_elapsed} calendar days) - well below "
            f"the {MIN_DAYS_FOR_MEANINGFUL_METRICS}-day floor for these metrics to mean anything. Treat every "
            "number below as illustrative-of-the-mechanism only, not a real performance read yet."
        ))

    return {
        "start_date": nav.index[0].strftime("%Y-%m-%d"),
        "end_date": nav.index[-1].strftime("%Y-%m-%d"),
        "days_elapsed": days_elapsed,
        "trading_days_used": len(daily_returns),
        "insufficient_history": insufficient_history,
        "starting_value": round(starting_cash, 2),
        "ending_value": round(float(nav.iloc[-1]), 2),
        "cagr_pct": round(cagr * 100, 2) if cagr is not None else None,
        "sharpe_ratio": round(sharpe, 3) if sharpe is not None else None,
        "sortino_ratio": round(sortino, 3) if sortino is not None else None,
        "information_ratio_vs_sp500": round(information_ratio, 3) if information_ratio is not None else None,
        "max_drawdown_pct": round(max_dd * 100, 2),
        "nav_series": [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)} for d, v in nav.items()],
        "limitations": limitations,
    }
