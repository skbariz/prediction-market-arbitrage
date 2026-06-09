import os
from dotenv import load_dotenv

load_dotenv()

KALSHI_API_KEY_ID = os.getenv("KALSHI_API_KEY_ID", "")
KALSHI_PRIVATE_KEY = os.getenv("KALSHI_PRIVATE_KEY", "").replace("\\n", "\n")
KALSHI_BASE_URL = os.getenv("KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")

POLY_PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
POLY_API_KEY = os.getenv("POLY_API_KEY", "")
POLY_API_SECRET = os.getenv("POLY_API_SECRET", "")
POLY_PASSPHRASE = os.getenv("POLY_PASSPHRASE", "")
POLY_CLOB_URL = os.getenv("POLY_CLOB_URL", "https://clob.polymarket.com")

MIN_PROFIT_PCT = float(os.getenv("MIN_PROFIT_PCT", "0.02"))
MAX_POSITION_USD = float(os.getenv("MAX_POSITION_USD", "50.0"))
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "10"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# Only consider markets resolving within this many days (ideal=7, hard max=14)
MAX_DAYS_TO_RESOLUTION = min(int(os.getenv("MAX_DAYS_TO_RESOLUTION", "7")), 14)

MATCH_SCORE_THRESHOLD = 80  # Minimum fuzzy-match score (0-100) to consider markets the same event
