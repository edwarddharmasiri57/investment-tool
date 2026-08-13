"""
Fama-French multi-factor regression - regresses a stock's historical monthly
excess returns against the Fama-French 5 factors (Mkt-RF, SMB, HML, RMW, CMA)
plus the Carhart momentum factor (Mom), via OLS. Standard academic/CFA-
curriculum methodology (Fama & French 2015; Carhart 1997), not an invented
model - source data is Kenneth French's Data Library (Dartmouth, free/public
CSVs): https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html

Factor CSVs are cached locally (data/fama_french_cache.json) and refreshed
if the cache is more than 30 days old, since French updates this data
infrequently (monthly, with a reporting lag).
"""
import io
import json
import os
import re
import time
import zipfile

import numpy as np
import requests
import yfinance as yf

from app.config import DATA_DIR

FIVE_FACTOR_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip"
MOMENTUM_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip"
FACTOR_CACHE_PATH = os.path.join(DATA_DIR, "fama_french_cache.json")
FACTOR_CACHE_MAX_AGE_DAYS = 30
MIN_MONTHS_FOR_REGRESSION = 24  # ~2 years of overlapping monthly data minimum for a meaningful regression
FACTOR_NAMES = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]

METHODOLOGY = (
    "Fama-French 5-factor model (Fama & French, 2015) + Carhart momentum factor (Carhart, 1997), "
    "OLS regression on monthly excess returns. Factor data: Kenneth French Data Library, Dartmouth."
)


def _download_csv_from_zip(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open(zf.namelist()[0]) as f:
            return f.read().decode("utf-8", errors="replace")


def _parse_monthly_section(csv_text: str, header_marker: str) -> dict[str, list[float]]:
    """Parses only the MONTHLY (YYYYMM-keyed) section of a French Data Library
    CSV, stopping at the "Annual Factors" section further down the same file."""
    lines = csv_text.splitlines()
    # Match the CSV header row itself (starts with a comma then the marker), not the
    # descriptive prose above it, which can contain the marker word too (e.g. the
    # momentum file's blurb starts with "Mom    is the average of the returns...").
    header_idx = next((i for i, line in enumerate(lines) if line.strip().startswith("," + header_marker)), None)
    if header_idx is None:
        raise ValueError(f"Couldn't find '{header_marker}' header row in Fama-French CSV.")

    result = {}
    for line in lines[header_idx + 1:]:
        parts = [p.strip() for p in line.split(",")]
        if not parts or not re.match(r"^\d{6}$", parts[0]):
            break  # blank line / "Annual Factors" section / trailing copyright text
        result[parts[0]] = [float(v) for v in parts[1:]]
    return result


def _fetch_factor_data() -> dict:
    five = _parse_monthly_section(_download_csv_from_zip(FIVE_FACTOR_URL), "Mkt-RF")
    mom = _parse_monthly_section(_download_csv_from_zip(MOMENTUM_URL), "Mom")

    factors = {}
    for period, vals in five.items():
        if period not in mom:
            continue
        mkt_rf, smb, hml, rmw, cma, rf = vals
        factors[period] = {"Mkt-RF": mkt_rf, "SMB": smb, "HML": hml, "RMW": rmw, "CMA": cma, "RF": rf, "Mom": mom[period][0]}
    return factors


def _load_factor_cache() -> dict:
    if os.path.exists(FACTOR_CACHE_PATH):
        with open(FACTOR_CACHE_PATH, "r") as f:
            cache = json.load(f)
        if (time.time() - cache["fetched_at"]) / 86400 <= FACTOR_CACHE_MAX_AGE_DAYS:
            return cache["factors"]

    factors = _fetch_factor_data()
    with open(FACTOR_CACHE_PATH, "w") as f:
        json.dump({"fetched_at": time.time(), "factors": factors}, f, indent=2)
    return factors


def get_factor_exposures(ticker: str, years: int = 5) -> dict:
    ticker = ticker.upper().strip()
    factors = _load_factor_cache()

    try:
        hist = yf.Ticker(ticker).history(period=f"{years}y", interval="1mo")
    except Exception as e:
        raise ValueError(f"Couldn't fetch price history for '{ticker}' ({e}).")
    if hist.empty or len(hist) < MIN_MONTHS_FOR_REGRESSION:
        raise ValueError(
            f"Not enough monthly price history for '{ticker}' to run a factor regression "
            f"(need >= {MIN_MONTHS_FOR_REGRESSION} months)."
        )

    monthly_returns = hist["Close"].pct_change().dropna()

    y, X, matched_periods = [], [], []
    for ts, ret in monthly_returns.items():
        period = ts.strftime("%Y%m")
        if period not in factors:
            continue
        f = factors[period]
        y.append(ret * 100 - f["RF"])  # stock return in %, minus the risk-free rate = excess return
        X.append([f[name] for name in FACTOR_NAMES])
        matched_periods.append(period)

    if len(y) < MIN_MONTHS_FOR_REGRESSION:
        raise ValueError(
            f"Only {len(y)} months of overlapping stock/factor data for '{ticker}' - "
            f"need >= {MIN_MONTHS_FOR_REGRESSION} for a meaningful regression."
        )

    y_arr = np.array(y)
    X_with_const = np.column_stack([np.ones(len(X)), np.array(X)])
    coeffs, _, _, _ = np.linalg.lstsq(X_with_const, y_arr, rcond=None)
    alpha, betas = coeffs[0], coeffs[1:]

    y_pred = X_with_const @ coeffs
    ss_res = np.sum((y_arr - y_pred) ** 2)
    ss_tot = np.sum((y_arr - y_arr.mean()) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else None

    return {
        "ticker": ticker,
        "methodology": METHODOLOGY,
        "months_used": len(y),
        "period_range": f"{matched_periods[0]}-{matched_periods[-1]}",
        "alpha_monthly_pct": round(float(alpha), 4),
        "factor_loadings": {name: round(float(b), 4) for name, b in zip(FACTOR_NAMES, betas)},
        "r_squared": round(float(r_squared), 4) if r_squared is not None else None,
        "limitations": [
            "OLS via numpy.linalg.lstsq - no p-values/standard errors computed, so individual factor "
            "loadings' statistical significance isn't assessed here, only point estimates plus overall R-squared.",
            f"Monthly returns over up to the last {years} years - factor loadings are known to drift over time "
            "as a company's risk profile changes, so this is a historical-average exposure, not necessarily "
            "representative of current/forward exposure.",
            "Fama-French factor data is cached locally for up to 30 days - may lag French's site by that much.",
        ],
    }
