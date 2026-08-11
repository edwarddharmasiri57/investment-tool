from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import DISCLAIMER
from app.data_service import fetch_company_data
from app.scoring_service import score_company
from app.research_service import generate_research_note
from app import storage

app = FastAPI(
    title="Investment Research Backend",
    description="Local screening & research tool. Not financial advice.",
    version="0.1.0",
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
    return {"data": data, "scores": scores, "disclaimer": DISCLAIMER}


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


@app.get("/api/watchlist")
def get_watchlist():
    return {"watchlist": storage.get_watchlist()}


@app.post("/api/watchlist")
def add_watchlist(req: WatchlistRequest):
    return {"watchlist": storage.add_to_watchlist(req.ticker)}


@app.delete("/api/watchlist/{ticker}")
def remove_watchlist(ticker: str):
    return {"watchlist": storage.remove_from_watchlist(ticker)}
