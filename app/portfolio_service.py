"""
A simulated/demo paper-trading journal - NOT a real brokerage connection.
Trades are logged manually by the user (this is a journal, not an execution
engine); positions and P&L are computed from that log using the standard
weighted-average-cost method.

DESIGN NOTE for a future Trading212 swap: get_positions()/get_portfolio_summary()
return a deliberately generic shape (ticker, quantity, avg_cost, current_price,
unrealized_pnl, unrealized_pnl_pct, total_value, ...) that a real brokerage
position feed would also naturally produce. When real T212 data replaces this
manual journal, only the internals of this module should need to change - the
frontend and the response shape should not. No T212 API integration exists
here yet (that needs proper OAuth/secure credential handling, not a plain
API key in .env - deliberately out of scope for this module).

Trades are processed in the order they were LOGGED (insertion order), not
re-sorted by the `date` field - a deliberate simplification for a manual
journal tool. If you're backfilling history out of chronological order, log
entries in the order they actually happened for accurate avg-cost/validation.
"""
import json
import os
import time
from datetime import datetime, timezone

import yfinance as yf

from app.config import PORTFOLIO_PATH, PLANNED_TRADES_PATH, PORTFOLIO_STARTING_CASH

VALID_ACTIONS = {"BUY", "SELL"}
_PRICE_CACHE: dict[str, tuple[float, float]] = {}
_PRICE_CACHE_TTL_SECONDS = 15 * 60


def _load_portfolio() -> dict:
    if not os.path.exists(PORTFOLIO_PATH):
        return {"starting_cash": PORTFOLIO_STARTING_CASH, "cash": PORTFOLIO_STARTING_CASH, "trades": []}
    with open(PORTFOLIO_PATH, "r") as f:
        return json.load(f)


def _save_portfolio(portfolio: dict):
    with open(PORTFOLIO_PATH, "w") as f:
        json.dump(portfolio, f, indent=2)


def _compute_holdings(trades: list[dict]) -> dict[str, dict]:
    """Weighted-average-cost method. Returns {ticker: {quantity, total_cost}} -
    avg_cost = total_cost/quantity. Selling doesn't change the avg cost of the
    remaining shares, only reduces quantity/total_cost proportionally.
    """
    holdings: dict[str, dict] = {}
    for t in trades:
        h = holdings.setdefault(t["ticker"], {"quantity": 0.0, "total_cost": 0.0})
        if t["action"] == "BUY":
            h["total_cost"] += t["quantity"] * t["price"]
            h["quantity"] += t["quantity"]
        else:  # SELL
            avg_cost = h["total_cost"] / h["quantity"] if h["quantity"] > 0 else 0.0
            h["total_cost"] -= avg_cost * t["quantity"]
            h["quantity"] -= t["quantity"]
    return holdings


def log_trade(ticker: str, action: str, quantity: float, price: float, date: str, notes: str = "") -> dict:
    ticker = ticker.upper().strip()
    action = action.upper().strip()
    if action not in VALID_ACTIONS:
        raise ValueError(f"action must be one of {sorted(VALID_ACTIONS)}, got '{action}'.")
    if quantity <= 0:
        raise ValueError("quantity must be positive.")
    if price <= 0:
        raise ValueError("price must be positive.")

    portfolio = _load_portfolio()
    cost = quantity * price

    if action == "BUY":
        if cost > portfolio["cash"]:
            raise ValueError(
                f"Insufficient simulated cash: trade costs {cost:.2f} but only {portfolio['cash']:.2f} available."
            )
        portfolio["cash"] -= cost
    else:  # SELL
        held = _compute_holdings(portfolio["trades"]).get(ticker, {"quantity": 0.0})["quantity"]
        if quantity > held + 1e-9:
            raise ValueError(f"Insufficient simulated shares: trying to sell {quantity} but only {held} held.")
        portfolio["cash"] += cost

    entry = {
        "id": len(portfolio["trades"]) + 1,
        "ticker": ticker,
        "action": action,
        "quantity": quantity,
        "price": price,
        "date": date,
        "notes": notes,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    portfolio["trades"].append(entry)
    _save_portfolio(portfolio)
    return entry


def _get_live_price(ticker: str) -> float | None:
    cached = _PRICE_CACHE.get(ticker)
    if cached and time.time() - cached[0] <= _PRICE_CACHE_TTL_SECONDS:
        return cached[1]
    try:
        price = float(yf.Ticker(ticker).fast_info["lastPrice"])
    except Exception:
        return None
    _PRICE_CACHE[ticker] = (time.time(), price)
    return price


def get_positions() -> list[dict]:
    portfolio = _load_portfolio()
    holdings = _compute_holdings(portfolio["trades"])

    positions = []
    for ticker, h in holdings.items():
        if h["quantity"] <= 1e-9:
            continue  # fully closed position
        avg_cost = h["total_cost"] / h["quantity"]
        current_price = _get_live_price(ticker)
        market_value = current_price * h["quantity"] if current_price is not None else None
        unrealized_pnl = (current_price - avg_cost) * h["quantity"] if current_price is not None else None
        unrealized_pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if current_price is not None and avg_cost else None

        positions.append({
            "ticker": ticker,
            "quantity": round(h["quantity"], 6),
            "avg_cost": round(avg_cost, 4),
            "current_price": round(current_price, 4) if current_price is not None else None,
            "market_value": round(market_value, 2) if market_value is not None else None,
            "unrealized_pnl": round(unrealized_pnl, 2) if unrealized_pnl is not None else None,
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2) if unrealized_pnl_pct is not None else None,
        })

    positions.sort(key=lambda p: p["ticker"])
    return positions


def get_portfolio_summary() -> dict:
    portfolio = _load_portfolio()
    positions = get_positions()

    positions_value = sum(p["market_value"] for p in positions if p["market_value"] is not None)
    cash = portfolio["cash"]
    total_value = cash + positions_value
    starting_cash = portfolio["starting_cash"]
    total_pnl = total_value - starting_cash
    total_pnl_pct = (total_pnl / starting_cash * 100) if starting_cash else None

    allocation = [
        {"ticker": p["ticker"], "pct_of_portfolio": round(p["market_value"] / total_value * 100, 2)}
        for p in positions if p["market_value"] is not None and total_value
    ]
    if total_value:
        allocation.append({"ticker": "CASH", "pct_of_portfolio": round(cash / total_value * 100, 2)})

    max_position_weight_pct = max((a["pct_of_portfolio"] for a in allocation if a["ticker"] != "CASH"), default=None)
    health = _compute_health_score(total_pnl_pct, max_position_weight_pct)

    return {
        "is_simulated": True,
        "account_type": "Simulated/demo paper account - not a real brokerage connection.",
        "starting_cash": starting_cash,
        "cash": round(cash, 2),
        "positions_value": round(positions_value, 2),
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2) if total_pnl_pct is not None else None,
        "num_positions": len(positions),
        "allocation": allocation,
        "health_score": health,
    }


HEALTH_WEIGHTS = {"pnl": 0.6, "diversification": 0.4}


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def _score_higher_is_better(value, bad, good):
    if value is None:
        return None
    if value >= good:
        return 100.0
    if value <= bad:
        return 0.0
    return _clamp(100 * (value - bad) / (good - bad))


def _score_lower_is_better(value, good, bad):
    if value is None:
        return None
    if value <= good:
        return 100.0
    if value >= bad:
        return 0.0
    return _clamp(100 * (bad - value) / (bad - good))


def _compute_health_score(total_pnl_pct: float | None, max_position_weight_pct: float | None) -> dict:
    """A simple, transparent 0-100 "portfolio health" score - not a standard
    industry metric, just this project's own composite, in the same style as
    scoring_service.py: independently None-able sub-scores, linear clamps,
    weighted average over whatever's available (no ML, no black box).

    - pnl: total return since inception, -20% or worse -> 0, +20% or better -> 100.
    - diversification: concentration risk via the single largest position's
      weight (excluding cash) - <=20% -> 100 (well diversified), >=80% -> 0
      (dangerously concentrated in one name), linear between. None when
      there are no open positions (nothing to concentrate).
    """
    sub_scores = {
        "pnl": _score_higher_is_better(total_pnl_pct, bad=-20, good=20),
        "diversification": _score_lower_is_better(max_position_weight_pct, good=20, bad=80),
    }
    available = {k: v for k, v in sub_scores.items() if v is not None}
    if available:
        weight_sum = sum(HEALTH_WEIGHTS[k] for k in available)
        composite = round(sum(v * HEALTH_WEIGHTS[k] for k, v in available.items()) / weight_sum, 1)
    else:
        composite = None

    return {
        "score": composite,
        "sub_scores": sub_scores,
        "methodology": "This project's own simple composite (not a standard industry metric): "
                       "60% total P&L since inception (-20%->0, +20%->100) + 40% diversification "
                       "(largest single position's weight, <=20%->100, >=80%->0).",
    }


def get_trade_log() -> list[dict]:
    return _load_portfolio()["trades"]


def get_starting_cash() -> float:
    return _load_portfolio()["starting_cash"]


def _load_planned_trades() -> list[dict]:
    if not os.path.exists(PLANNED_TRADES_PATH):
        return []
    with open(PLANNED_TRADES_PATH, "r") as f:
        return json.load(f)


def _save_planned_trades(planned: list[dict]):
    with open(PLANNED_TRADES_PATH, "w") as f:
        json.dump(planned, f, indent=2)


def log_planned_trade(ticker: str, action: str, target_date: str, target_price: float | None, notes: str = "") -> dict:
    ticker = ticker.upper().strip()
    action = action.upper().strip()
    if action not in VALID_ACTIONS:
        raise ValueError(f"action must be one of {sorted(VALID_ACTIONS)}, got '{action}'.")

    planned = _load_planned_trades()
    entry = {
        "id": len(planned) + 1,
        "ticker": ticker,
        "action": action,
        "target_date": target_date,
        "target_price": target_price,
        "notes": notes,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    planned.append(entry)
    _save_planned_trades(planned)
    return entry


def get_planned_trades() -> list[dict]:
    return _load_planned_trades()


def get_calendar(tickers: list[str]) -> dict:
    """Merges planned trades (all of them) with upcoming earnings dates for
    the given tickers into one chronological feed. Earnings dates come from
    yfinance's Ticker.calendar (estimated dates - not guaranteed accurate,
    companies can and do move confirmed earnings dates around).
    """
    events = []

    for pt in get_planned_trades():
        detail = f"{pt['action']} planned"
        if pt.get("target_price") is not None:
            detail += f" @ {pt['target_price']}"
        events.append({
            "type": "planned_trade",
            "date": pt["target_date"],
            "ticker": pt["ticker"],
            "detail": detail,
            "notes": pt.get("notes") or None,
        })

    errors = []
    for ticker in sorted(set(t.upper().strip() for t in tickers)):
        try:
            cal = yf.Ticker(ticker).calendar or {}
        except Exception as e:
            errors.append(f"{ticker}: {e}")
            continue
        for d in cal.get("Earnings Date") or []:
            events.append({
                "type": "earnings",
                "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                "ticker": ticker,
                "detail": "Earnings date (estimated - companies can move confirmed dates)",
                "notes": None,
            })

    events.sort(key=lambda e: e["date"])
    return {"events": events, "errors": errors}
