"""
database.py — All MongoDB operations for GitHub Control Bot
Each user has fully isolated data: token, repos, active_repo, state
"""

import motor.motor_asyncio
from config import MONGO_URI

# ─── Connection ───────────────────────────────────────────────────────────────
_client    = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
_db        = _client["github_control_bot"]

users_col  = _db["users"]    # github_token, repos[], active_repo
states_col = _db["states"]   # per-user conversation state

# ══════════════════════════════════════════════════════════════════════════════
#  USER HELPERS
# ══════════════════════════════════════════════════════════════════════════════

async def get_user(uid: int) -> dict:
    doc = await users_col.find_one({"_id": uid})
    return doc or {}

async def set_field(uid: int, field: str, value):
    await users_col.update_one(
        {"_id": uid}, {"$set": {field: value}}, upsert=True
    )

async def get_token(uid: int) -> str | None:
    doc = await get_user(uid)
    return doc.get("github_token")

async def set_token(uid: int, token: str):
    await set_field(uid, "github_token", token)

# ══════════════════════════════════════════════════════════════════════════════
#  REPO HELPERS
# ══════════════════════════════════════════════════════════════════════════════

async def get_repos(uid: int) -> list[dict]:
    """Returns list of {url, name, is_private} dicts."""
    doc = await get_user(uid)
    return doc.get("repos", [])

async def add_repo(uid: int, url: str, name: str = "", is_private: bool = False):
    """Add repo if not already saved. Returns True if added, False if duplicate."""
    repos = await get_repos(uid)
    urls  = [r["url"] for r in repos]
    if url in urls:
        return False
    repos.append({
        "url":        url,
        "name":       name or _short(url),
        "is_private": is_private,
    })
    await set_field(uid, "repos", repos)
    return True

async def update_repo(uid: int, index: int, url: str, name: str, is_private: bool):
    """Update repo at given index."""
    repos = await get_repos(uid)
    if 0 <= index < len(repos):
        repos[index] = {
            "url":        url,
            "name":       name or _short(url),
            "is_private": is_private,
        }
        await set_field(uid, "repos", repos)
        return True
    return False

async def delete_repo(uid: int, index: int) -> dict | None:
    """Delete repo at index. Returns deleted repo or None."""
    repos = await get_repos(uid)
    if 0 <= index < len(repos):
        removed = repos.pop(index)
        await set_field(uid, "repos", repos)
        # Clear active_repo if it was this one
        doc = await get_user(uid)
        if doc.get("active_repo") == removed["url"]:
            await set_field(uid, "active_repo", repos[0]["url"] if repos else None)
        return removed
    return None

async def get_active_repo(uid: int) -> str | None:
    """Get the currently selected active repo URL."""
    doc   = await get_user(uid)
    repos = doc.get("repos", [])
    active = doc.get("active_repo")
    # Validate active repo still exists
    urls = [r["url"] for r in repos]
    if active and active in urls:
        return active
    # Fall back to first repo
    return repos[0]["url"] if repos else None

async def set_active_repo(uid: int, url: str):
    await set_field(uid, "active_repo", url)

# ══════════════════════════════════════════════════════════════════════════════
#  STATE HELPERS  (conversation state machine — MongoDB backed)
# ══════════════════════════════════════════════════════════════════════════════

async def get_state(uid: int) -> dict:
    doc = await states_col.find_one({"_id": uid})
    return doc.get("state", {}) if doc else {}

async def set_state(uid: int, state: dict):
    await states_col.update_one(
        {"_id": uid}, {"$set": {"state": state}}, upsert=True
    )

async def clear_state(uid: int):
    await states_col.update_one(
        {"_id": uid}, {"$set": {"state": {}}}, upsert=True
    )

# ─── internal ─────────────────────────────────────────────────────────────────
def _short(url: str) -> str:
    import re
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else url
