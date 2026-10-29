from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Everything the app writes lives under DATA_DIR, a mounted volume in production.
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'feed.db'}")

# Without a key the feed still works, ranked by votes alone.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Set to 0 to serve the site without fetching feeds (tests, local design work)
RUN_FETCHER = os.getenv("RUN_FETCHER", "1") != "0"
REFRESH_MINUTES = float(os.getenv("REFRESH_MINUTES", "20"))
# The refresh button can't fetch more often than this
MIN_REFRESH_SECONDS = int(os.getenv("MIN_REFRESH_SECONDS", "120"))
# Stories nobody voted on are dropped after this many days; voted ones are
# kept, since they are what the taste is learned from.
KEEP_DAYS = int(os.getenv("KEEP_DAYS", "14"))
# Stories scoring below this are folded away (0-100)
HIDE_BELOW = int(os.getenv("HIDE_BELOW", "35"))
