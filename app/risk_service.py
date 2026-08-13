"""
Two classic credit/quality screens, computed from yfinance's annual
financial statements:

- Altman Z-Score: bankruptcy-risk formula from working capital, retained
  earnings, EBIT, market cap, and sales, all scaled by total assets/liabilities.
  This is the ORIGINAL 1968 coefficients (calibrated on public manufacturers) -
  Altman published separate Z'/Z'' variants for private companies and
  non-manufacturers that would fit financials/services companies better.
  Using one formula for every sector is a real simplification, flagged below.

- Piotroski F-Score: a 9-point checklist across profitability, leverage/
  liquidity, and operating efficiency, each signal worth 1 point, comparing
  the latest fiscal year to the prior one. This is what value investors use
  to screen out "cheap because it's dying" value traps.

Both need at least two fiscal years of annual statements; any individual
signal that can't be computed from available data is skipped (not scored
either way), and the response reports how many of the signals/inputs were
actually usable - do not read a low signal-count score as equivalent to a
fully-evaluated one.
"""
import yfinance as yf

Z_SAFE_THRESHOLD = 2.99
Z_DISTRESS_THRESHOLD = 1.81


def _row(df, label, col):
    if label not in df.index:
        return None
    v = df.loc[label, col]
    if v is None or v != v:  # NaN
        return None
    return float(v)


def _altman_z_score(ticker: str, info: dict, balance, income) -> dict:
    if balance.empty or income.empty:
        return {"z_score": None, "zone": None, "note": "No balance sheet / income statement data available."}

    col = sorted(balance.columns)[-1]
    inc_col = sorted(income.columns)[-1]

    total_assets = _row(balance, "Total Assets", col)
    working_capital = _row(balance, "Working Capital", col)
    retained_earnings = _row(balance, "Retained Earnings", col)
    total_liabilities = _row(balance, "Total Liabilities Net Minority Interest", col)
    ebit = _row(income, "EBIT", inc_col)
    sales = _row(income, "Total Revenue", inc_col)
    market_cap = info.get("marketCap")

    inputs = [total_assets, working_capital, retained_earnings, total_liabilities, ebit, sales, market_cap]
    if any(v is None for v in inputs) or not total_assets or not total_liabilities:
        return {"z_score": None, "zone": None, "note": "Missing one or more required line items - Z-Score not computed."}

    a = working_capital / total_assets
    b = retained_earnings / total_assets
    c = ebit / total_assets
    d = market_cap / total_liabilities
    e = sales / total_assets

    z = 1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e

    if z > Z_SAFE_THRESHOLD:
        zone = "safe"
    elif z > Z_DISTRESS_THRESHOLD:
        zone = "grey"
    else:
        zone = "distress"

    return {"z_score": round(z, 2), "zone": zone, "note": None}


def _piotroski_f_score(balance, income, cashflow) -> dict:
    if balance.empty or income.empty or cashflow.empty:
        return {"f_score": None, "signals_evaluated": 0, "signal_detail": {}, "note": "Insufficient statement data."}

    bal_cols = sorted(balance.columns)
    inc_cols = sorted(income.columns)
    cf_cols = sorted(cashflow.columns)
    if len(bal_cols) < 2 or len(inc_cols) < 2 or len(cf_cols) < 2:
        return {
            "f_score": None, "signals_evaluated": 0, "signal_detail": {},
            "note": "Fewer than 2 fiscal years of history available - can't compute year-over-year signals.",
        }

    cur_bal, prior_bal = bal_cols[-1], bal_cols[-2]
    cur_inc, prior_inc = inc_cols[-1], inc_cols[-2]
    cur_cf = cf_cols[-1]

    signals = {}

    total_assets_cur = _row(balance, "Total Assets", cur_bal)
    total_assets_prior = _row(balance, "Total Assets", prior_bal)
    net_income_cur = _row(income, "Net Income", cur_inc)
    net_income_prior = _row(income, "Net Income", prior_inc)
    cfo_cur = _row(cashflow, "Operating Cash Flow", cur_cf)

    # 1. Positive ROA
    if net_income_cur is not None and total_assets_cur:
        signals["positive_roa"] = net_income_cur / total_assets_cur > 0
    # 2. Positive operating cash flow
    if cfo_cur is not None:
        signals["positive_cfo"] = cfo_cur > 0
    # 3. ROA improving year-over-year
    if net_income_cur is not None and total_assets_cur and net_income_prior is not None and total_assets_prior:
        roa_cur = net_income_cur / total_assets_cur
        roa_prior = net_income_prior / total_assets_prior
        signals["roa_improving"] = roa_cur > roa_prior
    # 4. Earnings quality: CFO > Net Income
    if cfo_cur is not None and net_income_cur is not None:
        signals["cfo_exceeds_net_income"] = cfo_cur > net_income_cur

    long_term_debt_cur = _row(balance, "Long Term Debt", cur_bal)
    long_term_debt_prior = _row(balance, "Long Term Debt", prior_bal)
    # 5. Leverage decreasing
    if (long_term_debt_cur is not None and total_assets_cur
            and long_term_debt_prior is not None and total_assets_prior):
        signals["leverage_decreasing"] = (
            (long_term_debt_cur / total_assets_cur) < (long_term_debt_prior / total_assets_prior)
        )

    current_assets_cur = _row(balance, "Current Assets", cur_bal)
    current_liabilities_cur = _row(balance, "Current Liabilities", cur_bal)
    current_assets_prior = _row(balance, "Current Assets", prior_bal)
    current_liabilities_prior = _row(balance, "Current Liabilities", prior_bal)
    # 6. Current ratio improving
    if (current_assets_cur and current_liabilities_cur
            and current_assets_prior and current_liabilities_prior):
        signals["current_ratio_improving"] = (
            (current_assets_cur / current_liabilities_cur) > (current_assets_prior / current_liabilities_prior)
        )

    shares_cur = _row(balance, "Ordinary Shares Number", cur_bal)
    shares_prior = _row(balance, "Ordinary Shares Number", prior_bal)
    # 7. No new share issuance (diluted shares didn't increase)
    if shares_cur is not None and shares_prior is not None:
        signals["no_new_shares_issued"] = shares_cur <= shares_prior

    gross_profit_cur = _row(income, "Gross Profit", cur_inc)
    gross_profit_prior = _row(income, "Gross Profit", prior_inc)
    revenue_cur = _row(income, "Total Revenue", cur_inc)
    revenue_prior = _row(income, "Total Revenue", prior_inc)
    # 8. Gross margin improving
    if gross_profit_cur and revenue_cur and gross_profit_prior and revenue_prior:
        signals["gross_margin_improving"] = (
            (gross_profit_cur / revenue_cur) > (gross_profit_prior / revenue_prior)
        )
    # 9. Asset turnover improving
    if revenue_cur and total_assets_cur and revenue_prior and total_assets_prior:
        signals["asset_turnover_improving"] = (
            (revenue_cur / total_assets_cur) > (revenue_prior / total_assets_prior)
        )

    f_score = sum(1 for v in signals.values() if v)
    return {
        "f_score": f_score,
        "signals_evaluated": len(signals),
        "signal_detail": signals,
        "note": None if len(signals) == 9 else f"Only {len(signals)}/9 signals had enough data to evaluate.",
    }


def get_risk_profile(ticker: str) -> dict:
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

    altman = _altman_z_score(ticker, info, balance, income)
    piotroski = _piotroski_f_score(balance, income, cashflow)

    limitations = [
        "Altman Z-Score uses the original 1968 coefficients calibrated on public manufacturers - applying "
        "the same formula to financials, REITs, or asset-light services companies is a known mismatch "
        "(Altman's own Z'/Z'' variants for private/non-manufacturing firms aren't implemented here).",
        "Both scores compare only the latest two annual fiscal years available from yfinance (~5yr history "
        "cap) - a single unusual year can swing either score.",
        "Piotroski signals with missing underlying data are skipped, not scored as failing - check "
        "'signals_evaluated' before treating a low F-Score as a confirmed red flag rather than a data gap.",
    ]
    if info.get("sector") in ("Financial Services", "Real Estate"):
        limitations.append(
            f"'{ticker}' is in {info.get('sector')} - banks/insurers/REITs often lack a meaningful 'Working "
            "Capital' or 'Current Assets/Liabilities' split in their statements (capital IS the business), so "
            "the Altman Z-Score here may be null or unreliable for this ticker specifically."
        )

    return {
        "ticker": ticker,
        "altman_z_score": altman,
        "piotroski_f_score": piotroski,
        "limitations": limitations,
    }
