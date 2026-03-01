"""database.py — All MongoDB operations"""
import re
import motor.motor_asyncio
from config import MONGO_URI

_client    = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
_db        = _client["github_control_bot"]
users_col  = _db["users"]
states_col = _db["states"]

# ── User / Token ──────────────────────────────────────────────────────────────
async def get_user(uid: int) -> dict:
    return (await users_col.find_one({"_id": uid})) or {}

async def _set(uid: int, field: str, value):
    await users_col.update_one({"_id": uid}, {"$set": {field: value}}, upsert=True)

async def get_token(uid: int) -> str | None:
    return (await get_user(uid)).get("github_token")

async def set_token(uid: int, token: str):
    await _set(uid, "github_token", token)

# ── Repos ─────────────────────────────────────────────────────────────────────
async def get_repos(uid: int) -> list[dict]:
    return (await get_user(uid)).get("repos", [])

async def add_repo(uid: int, url: str, name: str = "", is_private: bool = False) -> bool:
    repos = await get_repos(uid)
    if url in [r["url"] for r in repos]:
        return False
    repos.append({"url": url, "name": name or _short(url), "is_private": is_private})
    await _set(uid, "repos", repos)
    return True

async def update_repo(uid: int, idx: int, url: str, name: str, is_private: bool):
    repos = await get_repos(uid)
    if 0 <= idx < len(repos):
        repos[idx] = {"url": url, "name": name or _short(url), "is_private": is_private}
        await _set(uid, "repos", repos)

async def delete_repo(uid: int, idx: int) -> dict | None:
    repos = await get_repos(uid)
    if 0 <= idx < len(repos):
        removed = repos.pop(idx)
        await _set(uid, "repos", repos)
        doc = await get_user(uid)
        if doc.get("active_repo") == removed["url"]:
            await _set(uid, "active_repo", repos[0]["url"] if repos else None)
        return removed
    return None

async def get_active_repo(uid: int) -> str | None:
    doc   = await get_user(uid)
    repos = doc.get("repos", [])
    active = doc.get("active_repo")
    urls   = [r["url"] for r in repos]
    if active and active in urls:
        return active
    return repos[0]["url"] if repos else None

async def set_active_repo(uid: int, url: str):
    await _set(uid, "active_repo", url)

# ── State ─────────────────────────────────────────────────────────────────────
async def get_state(uid: int) -> dict:
    doc = await states_col.find_one({"_id": uid})
    return doc.get("state", {}) if doc else {}

async def set_state(uid: int, state: dict):
    await states_col.update_one({"_id": uid}, {"$set": {"state": state}}, upsert=True)

async def clear_state(uid: int):
    await states_col.update_one({"_id": uid}, {"$set": {"state": {}}}, upsert=True)

def _short(url: str) -> str:
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else url

async def clean_user_data(uid: int):
    """Delete all user data: token, repos, active_repo, state."""
    await users_col.delete_one({"_id": uid})
    await states_col.delete_one({"_id": uid})

async def set_repos(uid: int, repos: list):
    """Directly set the full repos list."""
    await _set(uid, "repos", repos)
