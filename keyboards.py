"""
keyboards.py — All inline keyboards
KEY FIX: folder pickers use INDEX (0,1,2..) not folder name in callback_data
         → avoids Telegram's 64-byte callback_data limit
         → folder name is looked up from index at runtime
"""
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db
import git_utils as git
from config import REPOS_PER_PAGE


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📂 My Repos",    callback_data="show_repos"),
            InlineKeyboardButton("➕ Add Repo",     callback_data="add_repo"),
        ],
        [
            InlineKeyboardButton("🔍 Grep All",    callback_data="cmd_grep"),
            InlineKeyboardButton("🔍 Grep .py",    callback_data="cmd_grep_py"),
        ],
        [
            InlineKeyboardButton("✏️ Replace",     callback_data="cmd_replace"),
            InlineKeyboardButton("📁 Rename Dir",  callback_data="cmd_rename"),
        ],
        [
            InlineKeyboardButton("📦 Make ZIP",    callback_data="cmd_zip"),
            InlineKeyboardButton("🐙 Push→GitHub", callback_data="cmd_github_upload"),
        ],
        [
            InlineKeyboardButton("🚀 Git Push",    callback_data="cmd_git_push"),
            InlineKeyboardButton("📥 Clone",       callback_data="cmd_clone"),
        ],
        [
            InlineKeyboardButton("🔐 Set Token",       callback_data="cmd_set_token"),
            InlineKeyboardButton("📂 List Workspace",  callback_data="cmd_list"),
        ],
        [InlineKeyboardButton("❓ Help", callback_data="cmd_help")],
    ])


def folder_picker_kb(action_prefix: str) -> InlineKeyboardMarkup:
    """
    Builds a keyboard with one button per workspace folder.
    callback_data = "{action_prefix}:{index}"   ← index only, max ~20 bytes
    Folder name is resolved at handler time via get_workspace_folders()[index]
    """
    folders = git.get_workspace_folders()
    rows = []
    if folders:
        for i, folder in enumerate(folders):
            rows.append([InlineKeyboardButton(
                f"📁 {folder}",
                callback_data=f"{action_prefix}:{i}"   # SHORT: prefix:0, prefix:1 …
            )])
    else:
        rows.append([InlineKeyboardButton(
            "📂 Workspace empty — clone first",
            callback_data="cmd_clone"
        )])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="go_home")])
    return InlineKeyboardMarkup(rows)


async def repos_keyboard(uid: int, page: int = 0) -> InlineKeyboardMarkup:
    repos  = await db.get_repos(uid)
    active = await db.get_active_repo(uid)
    start  = page * REPOS_PER_PAGE
    chunk  = repos[start: start + REPOS_PER_PAGE]
    rows   = []

    for i, repo in enumerate(chunk):
        real_idx = start + i
        name     = (repo.get("name") or repo["url"])[:22]
        lock     = "🔒" if repo.get("is_private") else "🔓"
        tick     = " ✅" if repo["url"] == active else ""
        rows.append([
            InlineKeyboardButton(f"{lock} {name}{tick}", callback_data=f"repo_select:{real_idx}"),
            InlineKeyboardButton("✏️", callback_data=f"repo_edit:{real_idx}"),
            InlineKeyboardButton("🗑",  callback_data=f"repo_del:{real_idx}"),
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"repos_page:{page-1}"))
    if start + REPOS_PER_PAGE < len(repos):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"repos_page:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("➕ Add More", callback_data="add_repo"),
        InlineKeyboardButton("🔙 Back",     callback_data="go_home"),
    ])
    return InlineKeyboardMarkup(rows)


def repo_edit_keyboard(idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Change URL",       callback_data=f"re_url:{idx}")],
        [InlineKeyboardButton("🏷 Change Name",       callback_data=f"re_name:{idx}")],
        [InlineKeyboardButton("🔒 Toggle Private",    callback_data=f"re_priv:{idx}")],
        [InlineKeyboardButton("🗑 Delete This Repo",  callback_data=f"repo_del:{idx}")],
        [InlineKeyboardButton("🔙 Back to Repos",     callback_data="show_repos")],
    ])


def clone_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 With Token  (Private + Public)", callback_data="clone_with_token")],
        [InlineKeyboardButton("🌐 Without Token  (Public only)",   callback_data="clone_no_token")],
        [InlineKeyboardButton("🔙 Cancel", callback_data="go_home")],
    ])
