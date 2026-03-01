"""config.py — Loads all settings from .env file"""
import os
from pathlib import Path

# Load .env manually — no extra library needed
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            k, _, v = _line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def _req(key: str) -> str:
    val = os.environ.get(key, "")
    if not val or val.startswith("YOUR_"):
        raise SystemExit(f"\n❌ Missing required config: {key}\n   Set it in your .env file.\n")
    return val

API_ID         : int = int(_req("API_ID"))
API_HASH       : str = _req("API_HASH")
BOT_TOKEN      : str = _req("BOT_TOKEN")
OWNER_ID       : int = int(_req("OWNER_ID"))
MONGO_URI      : str = _req("MONGO_URI")
WORK_DIR       : str = os.environ.get("WORK_DIR", str(Path.home() / "bot_workspace"))
REPOS_PER_PAGE : int = int(os.environ.get("REPOS_PER_PAGE", "5"))

Path(WORK_DIR).mkdir(parents=True, exist_ok=True)
