import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PORT = int(os.getenv("PORT", "8000"))
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
WATCHLIST_PATH = os.path.join(DATA_DIR, "watchlist.json")

os.makedirs(DATA_DIR, exist_ok=True)

DISCLAIMER = (
    "Research and scoring output only. Not financial advice. "
    "Scores are a starting point for your own research, not a recommendation to buy or sell."
)
