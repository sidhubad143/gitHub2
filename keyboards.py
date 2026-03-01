"""
keyboards.py — All InlineKeyboard builders for GitHub Control Bot
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_repos, get_active_repo
from config import REPOS_PER_PAGE


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📂 My Repos",  callback_data="show_repos"),
            InlineKeyboardButton("➕ Add Repo",   callback_data="add_repo"),
        ],
        [
            InlineKeyboardButton("🔍 Grep All",   callback_data="cmd_grep"),
            InlineKeyboardButton("🔍 Grep .py",   callback_data="cmd_grep_py"),
        ],
        [
            InlineKeyboardButton("✏️ Replace",    callback_data="cmd_replace"),
            InlineKeyboardButton("📁 Rename Dir", callback_data="cmd_rename"),
        ],
        [
            InlineKeyboardButton("📦 Make ZIP",      callback_data="cmd_zip"),
            InlineKeyboardButton("🐙 ZIP→GitHub",    callback_data="cmd_github_upload"),
        ],
        [
            InlineKeyboardButton("🚀 Git Push",  callback_data="cmd_git_push"),
            InlineKeyboardButton("📥 Clone",     callback_data="cmd_clone"),
        ],
        [
            InlineKeyboardButton("🔐 Set Token",     callback_data="cmd_set_token"),
            InlineKeyboardButton("📂 List Workspace", callback_data="cmd_list"),
        ],
        [InlineKeyboardButton("❓ Help", callback_data="cmd_help")],
    ])


async def repos_keyboard(uid: int, page: int = 0) -> InlineKeyboardMarkup:
    """
    Repo panel keyboard.
    Each repo row: [📁 Name (✓ if active)] [✏️] [🗑]
    Bottom always has: [➕ Add More] [🔙 Back]
    """
    repos  = await get_repos(uid)
    active = await get_active_repo(uid)
    start  = page * REPOS_PER_PAGE
    chunk  = repos[start: start + REPOS_PER_PAGE]
    rows   = []

    for i, repo in enumerate(chunk):
        real_idx = start + i
        label    = (repo.get("name") or repo["url"])[:25]
        lock     = "🔒" if repo.get("is_private") else "🔓"
        tick     = " ✅" if repo["url"] == active else ""
        rows.append([
            InlineKeyboardButton(
                f"{lock} {label}{tick}",
                callback_data=f"repo_select:{real_idx}"
            ),
            InlineKeyboardButton("✏️", callback_data=f"repo_edit:{real_idx}"),
            InlineKeyboardButton("🗑",  callback_data=f"repo_del:{real_idx}"),
        ])

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"repos_page:{page-1}"))
    if start + REPOS_PER_PAGE < len(repos):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"repos_page:{page+1}"))
    if nav:
        rows.append(nav)

    # Always-visible bottom row
    rows.append([
        InlineKeyboardButton("➕ Add More", callback_data="add_repo"),
        InlineKeyboardButton("🔙 Back",    callback_data="go_home"),
    ])
    return InlineKeyboardMarkup(rows)


def repo_edit_keyboard(idx: int) -> InlineKeyboardMarkup:
    """Keyboard shown when editing a specific repo — confirm what to change."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Change URL",        callback_data=f"re_url:{idx}")],
        [InlineKeyboardButton("🏷 Change Name/Label", callback_data=f"re_name:{idx}")],
        [InlineKeyboardButton("🔒 Toggle Private",    callback_data=f"re_priv:{idx}")],
        [InlineKeyboardButton("🗑 Delete This Repo",  callback_data=f"repo_del:{idx}")],
        [InlineKeyboardButton("🔙 Back to Repos",     callback_data="show_repos")],
    ])


def clone_type_keyboard(idx: int | None = None, url: str = "") -> InlineKeyboardMarkup:
    """Ask user: clone with token or without token?"""
    cb_with    = f"clone_with_token:{idx}" if idx is not None else "clone_with_token_new"
    cb_without = f"clone_no_token:{idx}"   if idx is not None else "clone_no_token_new"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Clone with Token (Private/Public)", callback_data=cb_with)],
        [InlineKeyboardButton("🌐 Clone without Token (Public only)",  callback_data=cb_without)],
        [InlineKeyboardButton("🔙 Cancel", callback_data="go_home")],
    ])


def back_to_repos() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📂 My Repos", callback_data="show_repos"),
        InlineKeyboardButton("🏠 Home",     callback_data="go_home"),
    ]])
