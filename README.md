# Investment Research Dashboard

A full-stack investment research tool: a FastAPI backend that pulls real market data and
runs it through a set of standard quantitative-finance methods (DCF, CAPM, Fama-French
factors, Altman Z-Score, Piotroski F-Score, Markowitz portfolio optimization, and more),
and a React dashboard styled as a dark HUD command interface to explore it all.

It also includes a simulated paper-trading journal so you can log trades, track a demo
portfolio's real performance (Sharpe, Sortino, drawdown, CAGR — reconstructed from actual
logged trades against real historical prices), and compare it against optimizer-suggested
allocations.

**This is a personal research/portfolio project, not financial advice, and it does not
place real trades or connect to a real brokerage.** Every non-trivial calculation ships
with an explicit `limitations`/`methodology` field in its API response, spelling out what
it does and doesn't account for — the goal was to be honest about what each number means,
not to imply more precision than free data and a weekend can actually produce.

## What's in here

**Fundamentals & scoring**
- Value / Quality / Momentum / Growth composite score (0-100, simple linear math, no ML — see `app/scoring_service.py`)
- Extended composite that folds in DCF margin of safety and Piotroski F-Score, with an Altman Z-Score distress penalty applied on top
- Magic Formula (Greenblatt), Sloan Accruals Ratio, and Graham Number quality screens

**Valuation**
- DCF with a CAPM-derived discount rate (regression-based beta, not just yfinance's built-in figure)
- Comparable company analysis (EV/EBITDA, EV/Revenue, P/E vs. sector peers)
- Fama-French 5-factor + momentum regression (factor loadings, R², live data from Kenneth French's Data Library)

**Risk**
- Altman Z-Score (bankruptcy risk) and Piotroski F-Score (value-trap detection)
- Portfolio correlation matrix with high-correlation flags
- Mean-Variance Optimization (max-Sharpe) and Risk Parity weight suggestions, compared against actual holdings

**Sentiment & market context**
- News sentiment (Claude-classified headlines, batched per ticker)
- Social sentiment (StockTwits, Claude-classified)
- Market regime detection (VIX + 10y-2y treasury spread → Risk-On / Risk-Off / Elevated-Volatility)
- A transparent multi-signal blend (fundamentals + DCF + news + social) with each view's contribution shown, not a black box

**Discovery**
- Full S&P 500 scanner (static ticker list, extended scoring per company) on a daily APScheduler job, or triggered on demand
- Score movers — what changed since the last scan

**Simulated portfolio**
- Manual trade journal (clearly labeled as simulated, not real execution) with weighted-average cost basis
- Performance reconstructed from the actual trade log against real historical prices (Sharpe, Sortino, Information Ratio, max drawdown, CAGR)
- Calendar merging earnings dates, planned trades, and news events

**Backtesting**
- Does the composite score actually predict forward returns? Correlation + decile analysis across a ticker basket and date range, with explicit small-sample warnings

**Frontend**
- React + Vite dashboard with client-side routing (Overview, Portfolio, Screener, Calendar, Forecast, News, Risk)
- Dark "HUD" design system (custom CSS corner-bracket panels, animated radial health gauge, glow-pulse on live value changes, entrance animations via Framer Motion, charts via Recharts)

## Architecture

```
app/               FastAPI backend, one service module per concern
  main.py          route definitions
  *_service.py     one file per pillar (dcf, capm, risk, factor, blend, regime,
                    portfolio, backtest, universe, ...) — each independently testable
  config.py        shared constants (risk-free rate, ERP, file paths)
data/              runtime state (watchlist, portfolio journal, cached scans) — gitignored, auto-created on first run
frontend/          React + Vite SPA
  src/pages/       one component per route
  src/contexts/    shared watchlist + ticker-detail-modal state
  src/components/hud/  design-system primitives (panels, gauge, sparkline, ...)
```

**Backend:** FastAPI, yfinance (market data), Anthropic API (news/social sentiment classification,
qualitative research notes), numpy/scipy (regressions, portfolio optimization), pandas,
APScheduler (daily scan job).

**Frontend:** React 19, Vite, react-router-dom, Recharts, Framer Motion, Axios.

## Setup

### Backend

```bash
python -m venv venv
venv\Scripts\activate        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your Anthropic API key to `.env` (from https://console.anthropic.com/settings/keys) — needed
for `/api/research`, `/api/news`, and `/api/social`; everything else works without it.

```bash
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard: http://localhost:5173 (talks directly to the backend on :8000; CORS is wide open
since this is meant to run locally).

## API reference

| Area | Endpoints |
|---|---|
| Fundamentals | `GET /api/company/{ticker}`, `POST /api/screen` |
| Research | `POST /api/research/{ticker}` (Claude + web search) |
| Sentiment | `GET /api/news/{ticker}`, `GET /api/social/{ticker}`, `GET /api/trade-score/{ticker}` |
| Valuation | `GET /api/dcf/{ticker}`, `GET /api/comps/{ticker}`, `GET /api/capm/{ticker}`, `GET /api/factors/{ticker}` |
| Risk | `GET /api/risk/{ticker}` |
| Blend & regime | `GET /api/blend/{ticker}`, `GET /api/regime` |
| Discovery | `GET /api/discover`, `POST /api/discover/scan`, `GET /api/discover/movers` |
| Backtest | `POST /api/backtest` |
| History | `GET /api/score-history/{ticker}` |
| Watchlist | `GET/POST /api/watchlist`, `DELETE /api/watchlist/{ticker}` |
| Portfolio | `GET/POST /api/portfolio/trade`, `GET /api/portfolio/{positions,summary,trades,optimize,performance}`, `GET/POST /api/portfolio/planned` |
| Calendar | `GET /api/calendar` |

Every response includes a `disclaimer` field, and most include `limitations` or `methodology`
fields explaining exactly what the number does and doesn't capture — e.g. the DCF endpoint
tells you outright that its "WACC" is actually CAPM cost of equity, not a true weighted
average of debt and equity cost.

## Known limitations (documented in the code, not hidden)

- **yfinance rate limiting** — endpoints cache aggressively (15 min) to reduce this; a full
  S&P 500 scan realistically takes tens of minutes and paces itself between tickers.
- **Static S&P 500 ticker list** (`app/sp500_tickers.py`) — a manually-refreshed snapshot,
  will drift as real index membership changes.
- **FRED is unreachable from some environments** — the regime detector falls back to
  yfinance-only tickers (`^VIX`, `^TNX`, and a 2yr Treasury *futures* proxy) when it is.
- **Altman Z-Score uses the original 1968 coefficients**, calibrated for public
  manufacturers — a known-bad fit for banks/insurers/REITs, flagged explicitly per response.
- **Mean-Variance Optimization is long-only and highly sensitive to its historical return
  inputs** — shown alongside Risk Parity specifically because that method needs no return
  estimates and is more robust to estimation error.
- **No automated test suite** — this was built and verified via live manual testing against
  real market data at each step, not unit tests. A natural next step for anyone extending it.

## Not built yet

- Real Trading212 (or any brokerage) integration — the portfolio module's response shapes
  were deliberately kept generic so a real data source could replace the manual journal
  without changing the frontend, but no OAuth/credential handling exists yet.
- Automated tests.
