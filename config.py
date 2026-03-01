"""
config.py — All bot configuration loaded from .env file
Never hardcode credentials here. Edit .env instead.
"""

import os
from pathlib import Path

# ─── Load .env file manually (no extra lib needed) ────────────────────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                # Only set if not already in environment (env vars take priority)
                os.environ.setdefault(_key.strip(), _val.strip().strip('"').strip("'"))

# ══════════════════════════════════════════════════════════════════════════════
#  REQUIRED — bot won't start without these
# ══════════════════════════════════════════════════════════════════════════════

def _require(key: str) -> str:
    val = os.environ.get(key, "")
    if not val or val.startswith("YOUR_"):
        raise ValueError(
            f"\n❌ Missing required config: {key}\n"
            f"   Please set it in your .env file.\n"
            f"   See .env.example for reference.\n"
        )
    return val

API_ID    : int = int(_require("API_ID"))
API_HASH  : str = _require("API_HASH")
BOT_TOKEN : str = _require("BOT_TOKEN")
OWNER_ID  : int = int(_require("OWNER_ID"))
MONGO_URI : str = _require("MONGO_URI")

# ══════════════════════════════════════════════════════════════════════════════
#  OPTIONAL — with sensible defaults
# ══════════════════════════════════════════════════════════════════════════════

# Workspace directory where repos/zips are stored
WORK_DIR: str = os.environ.get("WORK_DIR", str(Path.home() / "bot_workspace"))

# Bot display name (used in messages)
BOT_NAME: str = os.environ.get("BOT_NAME", "GitHub Control Bot")

# Max repos shown per page in the repo panel
REPOS_PER_PAGE: int = int(os.environ.get("REPOS_PER_PAGE", "5"))

# ── Ensure workspace exists ───────────────────────────────────────────────────
Path(WORK_DIR).mkdir(parents=True, exist_ok=True)
