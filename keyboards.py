"""keyboards.py — All inline keyboards including dynamic folder pickers"""
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db
import git_utils as git
from config import REPOS_PER_PAGE


# ── Main Menu ─────────────────────────────────────────────────────────────────
def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📂 My Repos",   callback_data="show_repos"),
            InlineKeyboardButton("➕ Add Repo",    callback_data="add_repo"),
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
            InlineKeyboardButton("🐙 ZIP→GitHub",  callback_data="cmd_github_upload"),
        ],
        [
            InlineKeyboardButton("🚀 Git Push",    callback_data="cmd_git_push"),
            InlineKeyboardButton("📥 Clone",       callback_data="cmd_clone"),
        ],
        [
            InlineKeyboardButton("🔐 Set Token",      callback_data="cmd_set_token"),
            InlineKeyboardButton("📂 List Workspace",  callback_data="cmd_list"),
        ],
        [InlineKeyboardButton("❓ Help", callback_data="cmd_help")],
    ])


# ── Folder Picker — shows actual workspace folders as buttons ─────────────────
def folder_picker(action_prefix: str, extra_data: str = "") -> InlineKeyboardMarkup:
    """
    Shows clickable buttons for each folder in workspace.
    callback_data = f"{action_prefix}:{folder_name}"
    """
    folders = git.get_workspace_folders()
    rows = []
    if folders:
        for folder in folders:
            cb = f"{action_prefix}:{folder}"
            if extra_data:
                cb = f"{action_prefix}:{extra_data}:{folder}"
            rows.append([InlineKeyboardButton(f"📁 {folder}", callback_data=cb)])
    else:
        rows.append([InlineKeyboardButton("📂 Workspace empty — clone first", callback_data="cmd_clone")])

    rows.append([InlineKeyboardButton("🔙 Back", callback_data="go_home")])
    return InlineKeyboardMarkup(rows)


# ── Repo Panel ────────────────────────────────────────────────────────────────
async def repos_keyboard(uid: int, page: int = 0) -> InlineKeyboardMarkup:
    repos  = await db.get_repos(uid)
    active = await db.get_active_repo(uid)
    start  = page * REPOS_PER_PAGE
    chunk  = repos[start: start + REPOS_PER_PAGE]
    rows   = []

    for i, repo in enumerate(chunk):
        real_idx = start + i
        name     = (repo.get("name") or repo["url"])[:24]
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
        InlineKeyboardButton("➕ Add More",  callback_data="add_repo"),
        InlineKeyboardButton("🔙 Back",      callback_data="go_home"),
    ])
    return InlineKeyboardMarkup(rows)


# ── Repo Edit Sub-menu — for ONE specific repo ────────────────────────────────
def repo_edit_keyboard(idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Change URL",        callback_data=f"re_url:{idx}")],
        [InlineKeyboardButton("🏷 Change Name",        callback_data=f"re_name:{idx}")],
        [InlineKeyboardButton("🔒 Toggle Private",     callback_data=f"re_priv:{idx}")],
        [InlineKeyboardButton("🗑 Delete This Repo",   callback_data=f"repo_del:{idx}")],
        [InlineKeyboardButton("🔙 Back to Repos",      callback_data="show_repos")],
    ])


# ── Clone Type ────────────────────────────────────────────────────────────────
def clone_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 With Token  (Private + Public)",  callback_data="clone_with_token")],
        [InlineKeyboardButton("🌐 Without Token  (Public only)",    callback_data="clone_no_token")],
        [InlineKeyboardButton("🔙 Cancel", callback_data="go_home")],
    ])
