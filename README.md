# Investment Research Backend (v1)

A local FastAPI backend for screening and researching companies. Pulls fundamentals
from Yahoo Finance (free, via `yfinance`), scores companies on Value / Quality /
Momentum / Growth, and can generate a Claude-written, web-search-backed qualitative
research note for any ticker.

**This is a research tool, not financial advice, and it does not place trades.**
It's not connected to Trading212 yet — that's a natural next step once you're happy
with the screener (Trading212 has a public API for reading portfolio positions).

## Setup

```bash
cd investment-backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and add your Anthropic API key (from https://console.anthropic.com/settings/keys).
This is only needed for the `/api/research/{ticker}` endpoint — screening and scoring
work without it.

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000/docs — FastAPI auto-generates interactive API docs
where you can try every endpoint from the browser.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/api/company/{ticker}` | Full fundamentals + score for one company |
| POST | `/api/screen` | Score & rank a list of tickers, e.g. `{"tickers": ["AAPL", "MSFT", "NVDA"]}` |
| POST | `/api/research/{ticker}` | Claude + web search generates a structured research note (needs API key, costs a small amount per call) |
| GET/POST/DELETE | `/api/watchlist` | Save tickers you're tracking, stored in `data/watchlist.json` |

## How scoring works

Every company gets four 0-100 sub-scores (see `app/scoring_service.py` — it's deliberately
simple and readable, not a black box):

- **Value**: P/E, PEG, Price/Book — cheaper relative to earnings/book scores higher
- **Quality**: ROE, operating margin, debt/equity — more profitable, less levered scores higher
- **Momentum**: % above 200-day moving average, distance from 52-week high
- **Growth**: revenue growth, earnings growth

These combine into a weighted composite (default 30/30/20/20). Edit `DEFAULT_WEIGHTS`
in `scoring_service.py` if you want to tilt toward, say, pure value or pure momentum.

## Known gotcha: Yahoo Finance rate limiting

`yfinance` scrapes Yahoo Finance rather than using an official paid API, so if you screen
a lot of tickers back-to-back you may occasionally see `429`/transient errors. The backend
caches each ticker's data for 15 minutes to reduce this. If you keep hitting issues, the
free tier of Financial Modeling Prep or Alpha Vantage is a drop-in-ish replacement for
`data_service.py`.

## Next steps (not built yet)

- Trading212 API integration to pull real holdings into `/api/watchlist` automatically
- A simple frontend (or just use `/docs` for now)
- Historical score tracking (is this company's score improving or degrading over time?)
- Sector-relative scoring (compare a company only against its own sector, not the whole market)
