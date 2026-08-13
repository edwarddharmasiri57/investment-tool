"""
Scans a static universe (S&P 500 constituents, see app/sp500_tickers.py)
computing the FULL extended score - fundamentals + DCF + comps + Altman/
Piotroski risk - for every company, meant to run on a daily schedule
(wired up via APScheduler in main.py).

This is deliberately NOT what /api/company or /api/screen do. Scanning
~500 tickers means each one needs its own fundamentals + cashflow/balance/
income statement + peer-comps fetches - several thousand yfinance HTTP
calls per run. yfinance rate-limits aggressively (confirmed earlier in this
project), so this module paces itself with a short delay between tickers
and treats any single ticker's failure as a skip (logged to `errors`), not
an abort of the whole run. A full run realistically takes tens of minutes,
not seconds - this is a batch job, not something to call synchronously from
a user-facing request in the common case (a manual on-demand trigger exists
via run_universe_scan(tickers=...) with a small override list, mainly for
testing a handful of tickers without waiting for the full universe).

The S&P 500 list itself is a static, manually-refreshed snapshot (see
sp500_tickers.py docstring) - it will drift as index membership changes.
"""
import json
import os
import time
from datetime import datetime, timezone

from app.data_service import fetch_company_data
from app.dcf_service import get_dcf
from app.comps_service import get_comps
from app.risk_service import get_risk_profile
from app.scoring_service import score_company
from app.blend_service import get_blend
from app.regime_service import get_market_regime
from app.config import UNIVERSE_SCAN_PATH, PREVIOUS_UNIVERSE_SCAN_PATH
from app.sp500_tickers import SP500_TICKERS

SCAN_DELAY_SECONDS = 0.3  # small pacing delay between tickers to ease yfinance rate limits

_scan_in_progress = False


def _scan_one(ticker: str) -> dict | None:
    try:
        data = fetch_company_data(ticker)
    except ValueError:
        return None

    try:
        dcf = get_dcf(ticker)
    except ValueError:
        dcf = None
    try:
        comps = get_comps(ticker)
    except ValueError:
        comps = None
    try:
        risk = get_risk_profile(ticker)
    except ValueError:
        risk = None

    scores = score_company(data, dcf=dcf, risk=risk)

    try:
        blend = get_blend(ticker, data=data, dcf=dcf)
        blended_score = blend.get("blended_score")
    except ValueError:
        blended_score = None

    return {
        "ticker": ticker,
        "name": data.get("name"),
        "sector": data.get("sector"),
        "price": data.get("price"),
        "composite_score": scores["composite_score"],
        "blended_score": blended_score,
        "sub_scores": scores["sub_scores"],
        "data_completeness": scores["data_completeness"],
        "distress_penalty_applied": scores["distress_penalty_applied"],
        "risk_flag": scores["risk_flag"],
        "margin_of_safety_pct": dcf.get("margin_of_safety_pct") if dcf else None,
        "altman_zone": (risk or {}).get("altman_z_score", {}).get("zone"),
        "piotroski_f_score": (risk or {}).get("piotroski_f_score", {}).get("f_score"),
        "comps_premium_discount_pct": comps.get("premium_discount_pct") if comps else None,
    }


def run_universe_scan(tickers: list[str] | None = None) -> dict:
    global _scan_in_progress
    if _scan_in_progress:
        raise RuntimeError("A universe scan is already in progress - try again once it finishes.")

    universe = tickers if tickers is not None else SP500_TICKERS
    _scan_in_progress = True
    started = datetime.now(timezone.utc)
    results = []
    errors = []
    try:
        for ticker in universe:
            row = _scan_one(ticker.upper().strip())
            if row is not None:
                results.append(row)
            else:
                errors.append(ticker)
            time.sleep(SCAN_DELAY_SECONDS)
    finally:
        _scan_in_progress = False

    finished = datetime.now(timezone.utc)
    regime = get_market_regime()
    scan_result = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "universe_size": len(universe),
        "companies_scored": len(results),
        "market_regime": regime["regime"],
        "market_regime_reason": regime["reason"],
        "errors": errors,
        "results": results,
        "limitations": [
            "Universe is a static, manually-refreshed S&P 500 snapshot (see sp500_tickers.py) - will drift "
            "out of date as real index membership changes.",
            "Each company's composite here is the EXTENDED score (fundamentals + DCF + Piotroski, with an "
            "Altman distress penalty applied) - not directly comparable to /api/company's plain 4-factor score.",
            "Tickers that errored on any fetch are skipped entirely (see 'errors') rather than partially scored.",
        ],
    }
    _save_scan(scan_result)
    return scan_result


def _save_scan(scan_result: dict):
    # Rotate: whatever was the "latest" scan becomes "previous" before we overwrite it,
    # so get_movers() always has something to diff the new scan against (once a second
    # scan has ever run - the very first scan in a fresh install has no previous to compare).
    if os.path.exists(UNIVERSE_SCAN_PATH):
        with open(UNIVERSE_SCAN_PATH, "r") as f:
            previous = f.read()
        with open(PREVIOUS_UNIVERSE_SCAN_PATH, "w") as f:
            f.write(previous)

    with open(UNIVERSE_SCAN_PATH, "w") as f:
        json.dump(scan_result, f, indent=2)


def get_latest_scan() -> dict | None:
    if not os.path.exists(UNIVERSE_SCAN_PATH):
        return None
    with open(UNIVERSE_SCAN_PATH, "r") as f:
        return json.load(f)


def _get_previous_scan() -> dict | None:
    if not os.path.exists(PREVIOUS_UNIVERSE_SCAN_PATH):
        return None
    with open(PREVIOUS_UNIVERSE_SCAN_PATH, "r") as f:
        return json.load(f)


def get_movers(top_n: int = 10) -> dict:
    """Score movers between the two most recent scans (whatever their actual
    time gap is - could be a day under the normal 06:00 cron cadence, or
    minutes if scans were triggered manually back-to-back for testing).
    Needs at least two scans to have ever run; returns an explicit
    'has_data' flag rather than an error, since "no movers yet" is an
    expected, normal state for a fresh install, not a failure.
    """
    latest = get_latest_scan()
    previous = _get_previous_scan()

    if latest is None or previous is None:
        return {
            "has_data": False,
            "note": "Need at least two completed scans to compute movers - only "
                    f"{'one has' if latest else 'none have'} run so far.",
            "gainers": [],
            "losers": [],
        }

    prev_by_ticker = {r["ticker"]: r for r in previous["results"]}
    moves = []
    for row in latest["results"]:
        prev_row = prev_by_ticker.get(row["ticker"])
        if prev_row is None or row["composite_score"] is None or prev_row["composite_score"] is None:
            continue
        delta = round(row["composite_score"] - prev_row["composite_score"], 2)
        if delta == 0:
            continue
        moves.append({
            "ticker": row["ticker"],
            "name": row.get("name"),
            "composite_score": row["composite_score"],
            "previous_composite_score": prev_row["composite_score"],
            "delta": delta,
        })

    moves.sort(key=lambda m: m["delta"], reverse=True)
    gainers = [m for m in moves if m["delta"] > 0][:top_n]
    losers = list(reversed([m for m in moves if m["delta"] < 0][-top_n:]))

    return {
        "has_data": True,
        "compared_scan_at": previous["finished_at"],
        "latest_scan_at": latest["finished_at"],
        "tickers_compared": len(moves),
        "note": None,
        "gainers": gainers,
        "losers": losers,
    }
