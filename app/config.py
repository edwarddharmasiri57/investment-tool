import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PORT = int(os.getenv("PORT", "8000"))
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
WATCHLIST_PATH = os.path.join(DATA_DIR, "watchlist.json")
SCORE_HISTORY_PATH = os.path.join(DATA_DIR, "score_history.json")
UNIVERSE_SCAN_PATH = os.path.join(DATA_DIR, "universe_scan.json")
PREVIOUS_UNIVERSE_SCAN_PATH = os.path.join(DATA_DIR, "universe_scan_previous.json")
PORTFOLIO_PATH = os.path.join(DATA_DIR, "portfolio.json")
PLANNED_TRADES_PATH = os.path.join(DATA_DIR, "planned_trades.json")
PORTFOLIO_STARTING_CASH = float(os.getenv("PORTFOLIO_STARTING_CASH", "100000"))

# Shared market-assumption constants used by dcf_service.py and capm_service.py -
# kept in one place so both stay in sync instead of drifting apart.
RISK_FREE_RATE = 0.043  # ~10yr US Treasury yield, hardcoded as of 2026 - update periodically
EQUITY_RISK_PREMIUM = 0.05  # long-run US equity risk premium estimate, hardcoded

os.makedirs(DATA_DIR, exist_ok=True)

DISCLAIMER = (
    "Research and scoring output only. Not financial advice. "
    "Scores are a starting point for your own research, not a recommendation to buy or sell."
)
