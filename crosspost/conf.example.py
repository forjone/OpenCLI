"""Project configuration. Copy to conf.py and edit locally (gitignored)."""
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

# Where to store per-account cookie files
COOKIES_DIR = BASE_DIR / "cookies"

# Where uploads / artifacts are staged
DATA_DIR = BASE_DIR / "data"

# SQLite database
DATABASE_URL = f"sqlite:///{BASE_DIR / 'data' / 'crosspost.db'}"

# Optional local Chrome (otherwise patchright uses bundled)
LOCAL_CHROME_PATH = ""
LOCAL_CHROME_HEADLESS = False  # Default to headed during MVP — easier to debug
DEBUG_MODE = True

# XHS legacy server (only if you re-enable the xhs-lib path — not used by default)
XHS_SERVER = "http://127.0.0.1:11901"

# Claude API
ANTHROPIC_API_KEY = ""  # or read from env ANTHROPIC_API_KEY
LLM_MODEL = "claude-sonnet-4-6"
