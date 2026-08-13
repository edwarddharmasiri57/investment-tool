"""
Three established value/quality screens, layered onto /api/company/{ticker}
(not part of scoring_service.py's 0-100 composite - these are raw, well-known
figures shown alongside it, each labeled with its academic/practitioner source).

- Magic Formula (Greenblatt, "The Little Book That Beats the Market", 2005):
  Earnings Yield (EBIT/EV) + Return on Capital (EBIT/(Net Working Capital +
  Net Fixed Assets)). The real Magic Formula RANKS a universe of stocks by
  the combined rank of these two figures - a single ticker in isolation only
  gets the two raw inputs here, not a rank (there's no universe to rank
  against inside a single-ticker endpoint).

- Sloan Accruals Ratio (Sloan, 1996, "Do Stock Prices Fully Reflect
  Information in Accruals and Cash Flows About Future Earnings?", The
  Accounting Review): (Net Income - Operating Cash Flow) / Total Assets.
  High accruals (earnings running well ahead of actual cash flow) has
  historically correlated with lower forward returns - an earnings-quality
  red flag, not a valuation figure.

- Graham Number (Benjamin Graham, "The Intelligent Investor"): sqrt(22.5 *
  EPS * Book Value Per Share). A classic defensive-investor fair-value floor -
  only meaningful for profitable companies with positive book value;
  deliberately crude compared to a DCF, useful only as a sanity-check floor.
"""
import yfinance as yf

MAGIC_FORMULA_SOURCE = "Magic Formula (Greenblatt, 2005) - raw inputs only, not ranked against a universe."
SLOAN_ACCRUALS_SOURCE = "Sloan Accruals Ratio (Sloan, 1996, The Accounting Review)."
GRAHAM_NUMBER_SOURCE = "Graham Number (Benjamin Graham, The Intelligent Investor) - defensive-investor fair-value floor, not a primary valuation."
HIGH_ACCRUALS_THRESHOLD = 0.10  # commonly-cited practitioner rule-of-thumb, not a fixed universal number


def _latest_col(df):
    return sorted(df.columns)[-1] if not df.empty else None


def _row(df, label, col):
    if col is None or label not in df.index:
        return None
    v = df.loc[label, col]
    return None if v is None or v != v else float(v)


def _magic_formula(info: dict, balance, income) -> dict:
    inc_col = _latest_col(income)
    bal_col = _latest_col(balance)
    ebit = _row(income, "EBIT", inc_col)
    ev = info.get("enterpriseValue")

    earnings_yield = ebit / ev if ebit is not None and ev else None

    current_assets = _row(balance, "Current Assets", bal_col)
    current_liabilities = _row(balance, "Current Liabilities", bal_col)
    net_ppe = _row(balance, "Net PPE", bal_col)

    return_on_capital = None
    if None not in (ebit, current_assets, current_liabilities, net_ppe):
        invested_capital = (current_assets - current_liabilities) + net_ppe
        if invested_capital > 0:
            return_on_capital = ebit / invested_capital

    return {
        "source": MAGIC_FORMULA_SOURCE,
        "earnings_yield_pct": round(earnings_yield * 100, 2) if earnings_yield is not None else None,
        "return_on_capital_pct": round(return_on_capital * 100, 2) if return_on_capital is not None else None,
    }


def _sloan_accruals(balance, income, cashflow) -> dict:
    inc_col = _latest_col(income)
    bal_col = _latest_col(balance)
    cf_col = _latest_col(cashflow)

    net_income = _row(income, "Net Income", inc_col)
    operating_cash_flow = _row(cashflow, "Operating Cash Flow", cf_col)
    total_assets = _row(balance, "Total Assets", bal_col)

    ratio = None
    flag = None
    if net_income is not None and operating_cash_flow is not None and total_assets:
        ratio = (net_income - operating_cash_flow) / total_assets
        flag = "high_accruals_caution" if ratio > HIGH_ACCRUALS_THRESHOLD else "normal"

    return {
        "source": SLOAN_ACCRUALS_SOURCE,
        "accruals_ratio_pct": round(ratio * 100, 2) if ratio is not None else None,
        "flag": flag,
    }


def _graham_number(info: dict) -> dict:
    eps = info.get("trailingEps")
    book_value_per_share = info.get("bookValue")

    if not eps or not book_value_per_share or eps <= 0 or book_value_per_share <= 0:
        return {
            "source": GRAHAM_NUMBER_SOURCE,
            "value": None,
            "note": "Not meaningful - Graham's formula requires positive trailing EPS and positive book value per share.",
        }

    return {"source": GRAHAM_NUMBER_SOURCE, "value": round((22.5 * eps * book_value_per_share) ** 0.5, 2), "note": None}


def get_quality_screens(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
        balance = t.balance_sheet
        income = t.income_stmt
        cashflow = t.cashflow
    except Exception as e:
        raise ValueError(f"Couldn't fetch data for '{ticker}' ({e}).")

    if not info:
        raise ValueError(f"No data found for ticker '{ticker}'. Check the symbol is correct.")

    return {
        "magic_formula": _magic_formula(info, balance, income),
        "sloan_accruals_ratio": _sloan_accruals(balance, income, cashflow),
        "graham_number": _graham_number(info),
    }
