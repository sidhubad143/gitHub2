"""database.py — All MongoDB operations v5.0"""
import re
from datetime import datetime
import motor.motor_asyncio
from config import MONGO_URI

_client    = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
_db        = _client["github_control_bot"]
users_col  = _db["users"]
states_col = _db["states"]
logs_col   = _db["logs"]

# ── Internal helper ───────────────────────────────────────────────────────────
async def _set(uid: int, field: str, value):
    await users_col.update_one({"_id": uid}, {"$set": {field: value}}, upsert=True)

# ── User / Token ──────────────────────────────────────────────────────────────
async def get_user(uid: int) -> dict:
    return (await users_col.find_one({"_id": uid})) or {}

async def get_token(uid: int) -> str | None:
    return (await get_user(uid)).get("github_token")

async def set_token(uid: int, token: str):
    await _set(uid, "github_token", token)

async def get_all_users() -> list[dict]:
    return await users_col.find({}).to_list(length=10000)

# ── Repos ─────────────────────────────────────────────────────────────────────
async def get_repos(uid: int) -> list[dict]:
    return (await get_user(uid)).get("repos", [])

async def set_repos(uid: int, repos: list):
    await _set(uid, "repos", repos)

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
    doc    = await get_user(uid)
    repos  = doc.get("repos", [])
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

# ── Logs ──────────────────────────────────────────────────────────────────────
async def add_log(uid: int, username: str, action: str, detail: str = ""):
    await logs_col.insert_one({
        "uid":      uid,
        "username": username,
        "action":   action,
        "detail":   detail[:500],
        "time":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ts":       datetime.utcnow(),
    })

async def get_logs(uid: int = None, limit: int = 20) -> list[dict]:
    query  = {"uid": uid} if uid else {}
    cursor = logs_col.find(query).sort("ts", -1).limit(limit)
    return await cursor.to_list(length=limit)

async def get_all_logs(limit: int = 50) -> list[dict]:
    cursor = logs_col.find({}).sort("ts", -1).limit(limit)
    return await cursor.to_list(length=limit)

# ── Stats ─────────────────────────────────────────────────────────────────────
async def get_stats() -> dict:
    total_users = await users_col.count_documents({})
    total_logs  = await logs_col.count_documents({})
    push_count  = await logs_col.count_documents({"action": "git_push"})
    clone_count = await logs_col.count_documents({"action": "clone"})
    zip_count   = await logs_col.count_documents({"action": "zip_upload"})
    users       = await get_all_users()
    total_repos = sum(len(u.get("repos", [])) for u in users)
    return {
        "total_users":  total_users,
        "total_repos":  total_repos,
        "total_actions": total_logs,
        "git_pushes":   push_count,
        "clones":       clone_count,
        "zip_uploads":  zip_count,
    }

# ── Clean ─────────────────────────────────────────────────────────────────────
async def clean_user_data(uid: int):
    await users_col.delete_one({"_id": uid})
    await states_col.delete_one({"_id": uid})

# ── Helpers ───────────────────────────────────────────────────────────────────
def _short(url: str) -> str:
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else url
