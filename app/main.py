import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import DISCLAIMER
from app.data_service import fetch_company_data
from app.scoring_service import score_company, combine_scores
from app.research_service import generate_research_note
from app.news_service import get_news_sentiment
from app.social_service import get_social_sentiment
from app.backtest_service import run_backtest
from app.dcf_service import get_dcf
from app.comps_service import get_comps
from app.risk_service import get_risk_profile
from app.universe_service import run_universe_scan, get_latest_scan, get_movers
from app.blend_service import get_blend
from app.regime_service import get_market_regime
from app.factor_service import get_factor_exposures
from app.capm_service import get_capm
from app.quality_screens_service import get_quality_screens
from app.portfolio_optimization_service import get_portfolio_optimization
from app.performance_service import get_portfolio_performance
from app.portfolio_service import (
    log_trade, get_positions, get_portfolio_summary, get_trade_log,
    log_planned_trade, get_planned_trades, get_calendar,
)
from app import storage

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Daily full S&P 500 scan at 06:00 server-local time - see universe_service.py
    scheduler.add_job(run_universe_scan, "cron", hour=6, minute=0, id="daily_universe_scan", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Investment Research Backend",
    description="Local screening & research tool. Not financial advice.",
    version="0.1.0",
    lifespan=lifespan,
)

# Wide-open CORS since this only ever runs on localhost for personal use
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScreenRequest(BaseModel):
    tickers: list[str]


class WatchlistRequest(BaseModel):
    ticker: str


class BacktestRequest(BaseModel):
    tickers: list[str]
    start_date: str
    end_date: str


class ScanRequest(BaseModel):
    tickers: list[str] | None = None


class TradeRequest(BaseModel):
    ticker: str
    action: str
    quantity: float
    price: float
    date: str
    notes: str = ""


class PlannedTradeRequest(BaseModel):
    ticker: str
    action: str
    target_date: str
    target_price: float | None = None
    notes: str = ""


@app.get("/")
def root():
    return {"status": "ok", "message": "Investment research backend is running", "disclaimer": DISCLAIMER}


@app.get("/api/company/{ticker}")
def get_company(ticker: str):
    try:
        data = fetch_company_data(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    scores = score_company(data)
    try:
        quality_screens = get_quality_screens(ticker)
    except ValueError:
        quality_screens = None
    return {"data": data, "scores": scores, "quality_screens": quality_screens, "disclaimer": DISCLAIMER}


@app.post("/api/screen")
def screen(req: ScreenRequest):
    if not req.tickers:
        raise HTTPException(status_code=400, detail="Provide at least one ticker.")
    if len(req.tickers) > 25:
        raise HTTPException(status_code=400, detail="Limit to 25 tickers per screen to avoid rate limits.")

    results = []
    errors = []
    for ticker in req.tickers:
        try:
            data = fetch_company_data(ticker)
            scores = score_company(data)
            results.append({**data, **scores})
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})

    results.sort(key=lambda r: (r["composite_score"] is None, -(r["composite_score"] or 0)))
    return {"results": results, "errors": errors, "disclaimer": DISCLAIMER}


@app.post("/api/research/{ticker}")
def research(ticker: str):
    try:
        data = fetch_company_data(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        note = generate_research_note(ticker, data)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ticker": ticker.upper(), "fundamentals": data, "research": note, "disclaimer": DISCLAIMER}


@app.get("/api/news/{ticker}")
def news(ticker: str):
    try:
        result = get_news_sentiment(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/api/social/{ticker}")
def social(ticker: str):
    try:
        result = get_social_sentiment(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


async def _fetch_financials(ticker: str):
    try:
        return await asyncio.to_thread(fetch_company_data, ticker), None
    except ValueError as e:
        return None, str(e)


async def _fetch_news(ticker: str):
    try:
        return await asyncio.to_thread(get_news_sentiment, ticker), None
    except (ValueError, RuntimeError) as e:
        return None, str(e)


async def _fetch_social(ticker: str):
    try:
        return await asyncio.to_thread(get_social_sentiment, ticker), None
    except (ValueError, RuntimeError) as e:
        return None, str(e)


@app.get("/api/trade-score/{ticker}")
async def trade_score(ticker: str):
    (data, financials_error), (news, news_error), (social, social_error) = await asyncio.gather(
        _fetch_financials(ticker), _fetch_news(ticker), _fetch_social(ticker)
    )

    if data is None:
        raise HTTPException(status_code=404, detail=financials_error)

    financials = score_company(data)
    news_score = news["news_score"] if news else None
    social_score = social["social_score"] if social else None

    combined = combine_scores(financials["composite_score"], news_score, social_score)
    storage.log_score(ticker, combined["trade_score"], combined["pillar_scores"], financials["sub_scores"])

    return {
        "ticker": ticker.upper(),
        **combined,
        "financials": financials,
        "news_error": news_error,
        "social_error": social_error,
        "disclaimer": DISCLAIMER,
    }


@app.post("/api/backtest")
def backtest(req: BacktestRequest):
    if not req.tickers:
        raise HTTPException(status_code=400, detail="Provide at least one ticker.")
    if len(req.tickers) > 10:
        raise HTTPException(status_code=400, detail="Limit to 10 tickers per backtest - each one pulls full price + statement history.")
    try:
        result = run_backtest(req.tickers, req.start_date, req.end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/api/dcf/{ticker}")
def dcf(ticker: str):
    try:
        result = get_dcf(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/api/comps/{ticker}")
def comps(ticker: str):
    try:
        result = get_comps(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/api/risk/{ticker}")
def risk(ticker: str):
    try:
        result = get_risk_profile(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.post("/api/discover/scan")
def trigger_scan(req: ScanRequest | None = None):
    tickers = req.tickers if req else None

    if tickers:
        # Small on-demand subset (mainly for testing) - runs inline and returns results directly.
        try:
            result = run_universe_scan(tickers)
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return {**result, "disclaimer": DISCLAIMER}

    # Full S&P 500 - too slow (tens of minutes) to run inline on a request. Kick off as a
    # one-off background job on the same scheduler that runs the daily scan.
    scheduler.add_job(run_universe_scan, id="manual_universe_scan", replace_existing=True)
    return {
        "status": "started",
        "message": "Full S&P 500 scan started in the background - this takes tens of minutes. "
                    "Poll GET /api/discover for results once it finishes.",
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/discover/movers")
def discover_movers():
    return {**get_movers(), "disclaimer": DISCLAIMER}


@app.get("/api/discover")
def discover():
    scan = get_latest_scan()
    if scan is None:
        raise HTTPException(status_code=404, detail="No scan has run yet. POST /api/discover/scan to trigger one.")
    return {**scan, "disclaimer": DISCLAIMER}


@app.get("/api/blend/{ticker}")
def blend(ticker: str):
    try:
        result = get_blend(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/api/regime")
def regime():
    return {**get_market_regime(), "disclaimer": DISCLAIMER}


@app.post("/api/portfolio/trade")
def portfolio_trade(req: TradeRequest):
    try:
        entry = log_trade(req.ticker, req.action, req.quantity, req.price, req.date, req.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "status": "logged",
        "note": "This is a manual journal entry in a simulated/demo account - no real trade was executed.",
        "trade": entry,
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/portfolio/positions")
def portfolio_positions():
    return {
        "is_simulated": True,
        "account_type": "Simulated/demo paper account - not a real brokerage connection.",
        "positions": get_positions(),
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/portfolio/summary")
def portfolio_summary():
    return {**get_portfolio_summary(), "disclaimer": DISCLAIMER}


@app.get("/api/portfolio/trades")
def portfolio_trades():
    return {"trades": get_trade_log(), "disclaimer": DISCLAIMER}


@app.post("/api/portfolio/planned")
def portfolio_planned_trade(req: PlannedTradeRequest):
    try:
        entry = log_planned_trade(req.ticker, req.action, req.target_date, req.target_price, req.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "logged", "planned_trade": entry, "disclaimer": DISCLAIMER}


@app.get("/api/portfolio/planned")
def portfolio_planned_trades():
    return {"planned_trades": get_planned_trades(), "disclaimer": DISCLAIMER}


@app.get("/api/calendar")
def calendar():
    watchlist_tickers = storage.get_watchlist()
    portfolio_tickers = [p["ticker"] for p in get_positions()]
    tickers = sorted(set(watchlist_tickers) | set(portfolio_tickers))
    return {**get_calendar(tickers), "disclaimer": DISCLAIMER}


@app.get("/api/factors/{ticker}")
def factors(ticker: str):
    try:
        result = get_factor_exposures(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/api/capm/{ticker}")
def capm(ticker: str):
    try:
        result = get_capm(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/api/portfolio/optimize")
def portfolio_optimize():
    try:
        result = get_portfolio_optimization()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/api/portfolio/performance")
def portfolio_performance():
    try:
        result = get_portfolio_performance()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/api/score-history/{ticker}")
def score_history(ticker: str):
    return {"ticker": ticker.upper(), "history": storage.get_score_history(ticker), "disclaimer": DISCLAIMER}


@app.get("/api/watchlist")
def get_watchlist():
    return {"watchlist": storage.get_watchlist()}


@app.post("/api/watchlist")
def add_watchlist(req: WatchlistRequest):
    return {"watchlist": storage.add_to_watchlist(req.ticker)}


@app.delete("/api/watchlist/{ticker}")
def remove_watchlist(ticker: str):
    return {"watchlist": storage.remove_from_watchlist(ticker)}
