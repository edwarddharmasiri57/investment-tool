"""
Backtests whether the composite fundamentals score (scoring_service.score_company)
actually correlates with forward returns.

IMPORTANT CAVEAT: point-in-time fundamentals here are reconstructed from
yfinance's ANNUAL income statement / balance sheet, which yfinance only
exposes for ~5 fiscal years back per ticker. So the fundamentals half of the
score only changes once per fiscal year per ticker (the momentum sub-scores
still move daily, since price history goes back much further). This is a
coarse, small-sample tool for directional sanity-checking - not a rigorous
point-in-time factor study. Every response carries a "limitations" field and
per-horizon sample-size notes; read those before trusting the correlation
numbers.
"""
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

from app.scoring_service import score_company

HORIZONS_DAYS = {"1mo": 30, "3mo": 91, "6mo": 182}
MAX_ASOF_DATES_PER_TICKER = 12
MIN_SAMPLES_FOR_CORRELATION = 20
PRICE_LOOKUP_TOLERANCE_DAYS = 5

_FUNDAMENTALS_FIELDS = [
    "pe_ratio", "peg_ratio", "price_to_book", "roe",
    "operating_margin", "debt_to_equity",
    "pct_above_200d_ma", "pct_from_52w_high",
    "revenue_growth", "earnings_growth",
]


def _parse_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"'{s}' is not a valid date - use YYYY-MM-DD.")


def _quarterly_dates(start: datetime, end: datetime) -> list[datetime]:
    dates = []
    d = start
    while d <= end and len(dates) < MAX_ASOF_DATES_PER_TICKER:
        dates.append(d)
        d = d + pd.Timedelta(days=91)
    return dates


def _localized_ts(hist: pd.DataFrame, date: datetime) -> pd.Timestamp:
    ts = pd.Timestamp(date)
    tz = hist.index.tz
    return ts.tz_localize(tz) if tz is not None else ts


def _price_on_or_before(hist: pd.DataFrame, ts: pd.Timestamp):
    window = hist.loc[:ts]
    if window.empty:
        return None
    if (ts - window.index[-1]).days > PRICE_LOOKUP_TOLERANCE_DAYS:
        return None
    return float(window["Close"].iloc[-1])


def _price_on_or_after(hist: pd.DataFrame, ts: pd.Timestamp):
    window = hist.loc[ts:]
    if window.empty:
        return None
    if (window.index[0] - ts).days > PRICE_LOOKUP_TOLERANCE_DAYS:
        return None
    return float(window["Close"].iloc[0])


def _forward_returns(hist: pd.DataFrame, ts: pd.Timestamp, price: float) -> dict:
    returns = {}
    for label, days in HORIZONS_DAYS.items():
        future_price = _price_on_or_after(hist, ts + pd.Timedelta(days=days))
        if future_price is None or not price:
            returns[label] = None
        else:
            returns[label] = round(((future_price - price) / price) * 100, 2)
    return returns


def _reconstruct_fundamentals(hist, income, balance, asof_date: datetime):
    if income.empty or balance.empty:
        return None

    asof_ts = pd.Timestamp(asof_date)
    fiscal_dates = sorted(income.columns)
    eligible = [d for d in fiscal_dates if d <= asof_ts]
    if not eligible:
        return None
    fy = eligible[-1]
    prior_candidates = [d for d in fiscal_dates if d < fy]
    prior_fy = prior_candidates[-1] if prior_candidates else None

    def inc(row, col):
        try:
            v = income.loc[row, col]
        except KeyError:
            return None
        return None if pd.isna(v) else float(v)

    def bal(row, col):
        try:
            v = balance.loc[row, col]
        except KeyError:
            return None
        return None if pd.isna(v) else float(v)

    revenue = inc("Total Revenue", fy)
    operating_income = inc("Operating Income", fy)
    net_income = inc("Net Income", fy)
    diluted_eps = inc("Diluted EPS", fy)
    stockholders_equity = bal("Stockholders Equity", fy)
    total_debt = bal("Total Debt", fy)
    ordinary_shares = bal("Ordinary Shares Number", fy)

    price_ts = _localized_ts(hist, asof_date)
    price = _price_on_or_before(hist, price_ts)
    if price is None:
        return None

    pe_ratio = price / diluted_eps if diluted_eps and diluted_eps > 0 else None
    book_value_per_share = (
        stockholders_equity / ordinary_shares if stockholders_equity and ordinary_shares else None
    )
    price_to_book = price / book_value_per_share if book_value_per_share and book_value_per_share > 0 else None
    roe = net_income / stockholders_equity if net_income is not None and stockholders_equity else None
    operating_margin = operating_income / revenue if operating_income is not None and revenue else None
    debt_to_equity = (
        (total_debt / stockholders_equity) * 100 if total_debt is not None and stockholders_equity else None
    )

    revenue_growth = None
    earnings_growth = None
    if prior_fy is not None:
        prior_revenue = inc("Total Revenue", prior_fy)
        prior_net_income = inc("Net Income", prior_fy)
        if revenue is not None and prior_revenue:
            revenue_growth = (revenue - prior_revenue) / prior_revenue
        if net_income is not None and prior_net_income:
            earnings_growth = (net_income - prior_net_income) / prior_net_income

    ma_window = hist.loc[:price_ts].tail(200)
    pct_above_200d_ma = None
    if len(ma_window) >= 50:
        ma200 = float(ma_window["Close"].mean())
        if ma200:
            pct_above_200d_ma = round(((price - ma200) / ma200) * 100, 2)

    year_window = hist.loc[price_ts - pd.Timedelta(days=365):price_ts]
    pct_from_52w_high = None
    if not year_window.empty:
        high = float(year_window["Close"].max())
        if high:
            pct_from_52w_high = round(((price - high) / high) * 100, 2)

    return {
        "price": price,
        "fiscal_year_end": fy.strftime("%Y-%m-%d"),
        "pe_ratio": pe_ratio,
        "peg_ratio": None,  # not reconstructable without historical forward-growth estimates
        "price_to_book": price_to_book,
        "roe": roe,
        "operating_margin": operating_margin,
        "debt_to_equity": debt_to_equity,
        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,
        "pct_above_200d_ma": pct_above_200d_ma,
        "pct_from_52w_high": pct_from_52w_high,
    }


def _backtest_ticker(ticker: str, start: datetime, end: datetime) -> tuple[list[dict], str | None]:
    ticker = ticker.upper().strip()
    t = yf.Ticker(ticker)
    try:
        hist = t.history(period="max")
        income = t.income_stmt
        balance = t.balance_sheet
    except Exception as e:
        return [], f"Couldn't fetch data for '{ticker}' ({e})."

    if hist is None or hist.empty:
        return [], f"No price history for '{ticker}'."

    samples = []
    for asof in _quarterly_dates(start, end):
        fundamentals = _reconstruct_fundamentals(hist, income, balance, asof)
        if fundamentals is None:
            continue
        scores = score_company({k: fundamentals.get(k) for k in _FUNDAMENTALS_FIELDS})
        if scores["composite_score"] is None:
            continue
        ts = _localized_ts(hist, asof)
        forward = _forward_returns(hist, ts, fundamentals["price"])
        samples.append({
            "ticker": ticker,
            "asof_date": asof.strftime("%Y-%m-%d"),
            "fiscal_year_end": fundamentals["fiscal_year_end"],
            "composite_score": scores["composite_score"],
            "sub_scores": scores["sub_scores"],
            "forward_returns": forward,
        })

    if not samples:
        return [], (
            f"No reconstructable data points for '{ticker}' in this date range "
            "(yfinance's annual statements only go back ~5 fiscal years)."
        )
    return samples, None


def _correlate(samples: list[dict], horizon: str) -> dict:
    pairs = [
        (s["composite_score"], s["forward_returns"][horizon])
        for s in samples
        if s["forward_returns"].get(horizon) is not None
    ]
    n = len(pairs)
    if n < 3:
        return {"n": n, "correlation": None, "note": "Fewer than 3 samples with this horizon - correlation not computed."}

    scores_arr = np.array([p[0] for p in pairs])
    returns_arr = np.array([p[1] for p in pairs])
    if scores_arr.std() == 0 or returns_arr.std() == 0:
        corr = None
    else:
        corr = round(float(np.corrcoef(scores_arr, returns_arr)[0, 1]), 3)

    result = {"n": n, "correlation": corr}
    if n < MIN_SAMPLES_FOR_CORRELATION:
        result["note"] = (
            f"Only {n} samples for this horizon - well below a size where a correlation coefficient "
            "is meaningful. Treat this as directional/exploratory only, not statistical evidence."
        )
    return result


def _bucket_analysis(samples: list[dict], horizon: str) -> dict:
    pairs = [
        (s["composite_score"], s["forward_returns"][horizon])
        for s in samples
        if s["forward_returns"].get(horizon) is not None
    ]
    n = len(pairs)
    if n < 4:
        return {"n": n, "buckets": [], "note": "Fewer than 4 samples - not enough to bucket."}

    pairs.sort(key=lambda p: p[0])
    n_buckets = min(10, max(2, n // 4))
    bucket_size = max(1, n // n_buckets)
    buckets = []
    for i in range(n_buckets):
        lo = i * bucket_size
        hi = (i + 1) * bucket_size if i < n_buckets - 1 else n
        chunk = pairs[lo:hi]
        if not chunk:
            continue
        buckets.append({
            "bucket": i + 1,
            "n": len(chunk),
            "avg_composite_score": round(sum(c[0] for c in chunk) / len(chunk), 1),
            "avg_forward_return_pct": round(sum(c[1] for c in chunk) / len(chunk), 2),
        })

    note = None
    if n_buckets < 10:
        note = f"n={n} is too small for true deciles - grouped into {len(buckets)} buckets instead."
    return {"n": n, "buckets": buckets, "note": note}


def run_backtest(tickers: list[str], start_date: str, end_date: str) -> dict:
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if end <= start:
        raise ValueError("end_date must be after start_date.")
    if (datetime.now() - end).days < 30:
        raise ValueError(
            "end_date must be at least ~1 month in the past so forward returns have room to be measured "
            "(for the full 6-month horizon, end_date should be ~6+ months ago)."
        )

    all_samples = []
    errors = []
    for ticker in tickers:
        samples, error = _backtest_ticker(ticker, start, end)
        all_samples.extend(samples)
        if error:
            errors.append(error)

    correlations = {h: _correlate(all_samples, h) for h in HORIZONS_DAYS}
    buckets = {h: _bucket_analysis(all_samples, h) for h in HORIZONS_DAYS}

    return {
        "tickers_requested": [t.upper().strip() for t in tickers],
        "start_date": start_date,
        "end_date": end_date,
        "total_samples": len(all_samples),
        "correlations": correlations,
        "decile_analysis": buckets,
        "samples": all_samples,
        "errors": errors,
        "limitations": [
            "Fundamentals are reconstructed from yfinance's ANNUAL income statement/balance sheet, which "
            "yfinance only exposes for ~5 fiscal years back per ticker - so the fundamentals half of each "
            "score only changes once per fiscal year, not continuously point-in-time.",
            "peg_ratio needs historical forward analyst growth estimates, which yfinance doesn't expose "
            "as-of-date, so it is always excluded from the backtested score.",
            "Survivorship bias: only currently-listed tickers can be tested here, so failed/delisted "
            "companies are structurally excluded from the sample.",
            "Correlation and bucket results below a few dozen samples are exploratory/directional only - "
            "see each horizon's 'note' field for the sample-size caveat on this specific run.",
        ],
    }
