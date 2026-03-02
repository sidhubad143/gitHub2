"""keyboards.py — All inline keyboards v5.0"""
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ══ MAIN MENU ═════════════════════════════════════════════════════════════════
def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📂 My Repos",        callback_data="show_repos"),
            InlineKeyboardButton("🌐 GitHub Repos",    callback_data="cmd_gh_all_repos"),
        ],
        [
            InlineKeyboardButton("➕ Add Repo",         callback_data="add_repo"),
            InlineKeyboardButton("🆕 Create Repo",     callback_data="cmd_create_repo"),
        ],
        [
            InlineKeyboardButton("📥 Clone",           callback_data="cmd_clone"),
            InlineKeyboardButton("🚀 Git Push",        callback_data="cmd_push"),
        ],
        [
            InlineKeyboardButton("⬇️ Git Pull",        callback_data="cmd_pull"),
            InlineKeyboardButton("📤 Upload ZIP",      callback_data="cmd_upload_zip"),
        ],
        [
            InlineKeyboardButton("📦 Make ZIP",        callback_data="cmd_make_zip"),
            InlineKeyboardButton("🗂 File Manager",    callback_data="cmd_file_manager"),
        ],
        [
            InlineKeyboardButton("🔍 Grep Search",     callback_data="cmd_grep"),
            InlineKeyboardButton("✏️ Replace Text",    callback_data="cmd_replace"),
        ],
        [
            InlineKeyboardButton("🌿 Branches",        callback_data="cmd_branches"),
            InlineKeyboardButton("👥 Collaborators",   callback_data="cmd_collabs"),
        ],
        [
            InlineKeyboardButton("📎 Gists",           callback_data="cmd_gists"),
            InlineKeyboardButton("👤 Edit Profile",    callback_data="cmd_edit_profile"),
        ],
        [
            InlineKeyboardButton("🗑 Delete GH Repo",  callback_data="cmd_delete_gh_repo"),
            InlineKeyboardButton("📊 Bot Stats",       callback_data="cmd_stats"),
        ],
        [
            InlineKeyboardButton("🔐 Set Token",       callback_data="cmd_set_token"),
            InlineKeyboardButton("📋 My Logs",         callback_data="cmd_my_logs"),
        ],
        [
            InlineKeyboardButton("🧹 Clean My Data",   callback_data="cmd_clean_data"),
            InlineKeyboardButton("❓ Help",             callback_data="cmd_help"),
        ],
    ])

# ══ OWNER MENU (extra buttons for owner) ═════════════════════════════════════
def owner_extra_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 All Logs",        callback_data="owner_all_logs"),
            InlineKeyboardButton("📢 Broadcast",       callback_data="owner_broadcast"),
        ],
        [
            InlineKeyboardButton("👥 All Users",       callback_data="owner_all_users"),
            InlineKeyboardButton("🔙 Back",            callback_data="go_home"),
        ],
    ])

# ══ REPOS ═════════════════════════════════════════════════════════════════════
async def repos_keyboard(uid: int, page: int = 0):
    import database as db
    repos    = await db.get_repos(uid)
    active   = await db.get_active_repo(uid)
    PER_PAGE = 6
    start    = page * PER_PAGE
    chunk    = repos[start: start + PER_PAGE]
    rows     = []
    for i, r in enumerate(chunk):
        real_i = start + i
        name   = r.get("name") or r["url"].split("/")[-1]
        lock   = "🔒" if r.get("is_private") else "🔓"
        star   = "⭐" if r["url"] == active else ""
        rows.append([
            InlineKeyboardButton(f"{star}{lock} {name[:30]}", callback_data=f"repo_select:{real_i}"),
            InlineKeyboardButton("✏️", callback_data=f"repo_edit:{real_i}"),
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"repos_page:{page-1}"))
    if start + PER_PAGE < len(repos):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"repos_page:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("➕ Add Repo", callback_data="add_repo"),
                 InlineKeyboardButton("🔙 Back",     callback_data="go_home")])
    return InlineKeyboardMarkup(rows)

def repo_edit_keyboard(idx: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Change URL",          callback_data=f"re_url:{idx}"),
         InlineKeyboardButton("🏷 Change Name",         callback_data=f"re_name:{idx}")],
        [InlineKeyboardButton("🔒 Toggle Private",      callback_data=f"re_priv:{idx}"),
         InlineKeyboardButton("🗑 Remove from Bot List",callback_data=f"re_del:{idx}")],
        [InlineKeyboardButton("💥 Delete on GitHub",    callback_data=f"gh_del_repo:{idx}"),
         InlineKeyboardButton("🔙 Back",                callback_data="show_repos")],
    ])

def clone_type_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔓 Public (no token)", callback_data="clone_pub"),
         InlineKeyboardButton("🔐 With Token",        callback_data="clone_priv")],
        [InlineKeyboardButton("🔙 Cancel",             callback_data="go_home")],
    ])

# ══ FOLDER PICKER ══════════════════════════════════════════════════════════════
def folder_picker_kb(prefix: str):
    """Builds inline keyboard with workspace folder buttons."""
    import git_utils as git
    folders = git.get_workspace_folders()
    if not folders:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ No folders", callback_data="go_home")]])
    rows = []
    for i, f in enumerate(folders):
        rows.append([InlineKeyboardButton(f"📁 {f}", callback_data=f"{prefix}:{i}")])
    rows.append([InlineKeyboardButton("🔙 Cancel", callback_data="go_home")])
    return InlineKeyboardMarkup(rows)

# ══ BRANCHES ══════════════════════════════════════════════════════════════════
def branches_keyboard(branches: list, repo_idx: int):
    rows = []
    for i, b in enumerate(branches[:10]):
        rows.append([InlineKeyboardButton(f"🌿 {b}", callback_data=f"branch_info:{repo_idx}:{i}")])
    rows.append([
        InlineKeyboardButton("➕ New Branch",   callback_data=f"branch_create:{repo_idx}"),
        InlineKeyboardButton("🔀 Merge",        callback_data=f"branch_merge:{repo_idx}"),
    ])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="go_home")])
    return InlineKeyboardMarkup(rows)

def branch_action_keyboard(repo_idx: int, branch_idx: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Delete Branch", callback_data=f"branch_delete:{repo_idx}:{branch_idx}")],
        [InlineKeyboardButton("🔙 Back to Branches", callback_data=f"cmd_branches_repo:{repo_idx}")],
    ])

# ══ GISTS ═════════════════════════════════════════════════════════════════════
def gists_keyboard(gists: list):
    rows = []
    for i, g in enumerate(gists[:8]):
        files    = list(g.get("files", {}).keys())
        fname    = files[0] if files else "untitled"
        vis      = "🔓" if g.get("public") else "🔒"
        rows.append([InlineKeyboardButton(f"{vis} {fname[:30]}", callback_data=f"gist_view:{i}")])
    rows.append([
        InlineKeyboardButton("➕ New Gist", callback_data="gist_create"),
        InlineKeyboardButton("🔙 Back",     callback_data="go_home"),
    ])
    return InlineKeyboardMarkup(rows)

def gist_action_keyboard(gist_idx: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Delete Gist",  callback_data=f"gist_delete:{gist_idx}"),
         InlineKeyboardButton("🔙 Back",         callback_data="cmd_gists")],
    ])

# ══ COLLABS ═══════════════════════════════════════════════════════════════════
def collabs_repo_keyboard(repos: list):
    rows = []
    for i, r in enumerate(repos):
        name = r.get("name") or r["url"].split("/")[-1]
        rows.append([InlineKeyboardButton(f"📁 {name[:30]}", callback_data=f"collabs_repo:{i}")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="go_home")])
    return InlineKeyboardMarkup(rows)

def collabs_action_keyboard(repo_idx: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Collaborator",    callback_data=f"collab_add:{repo_idx}"),
         InlineKeyboardButton("➖ Remove Collaborator", callback_data=f"collab_remove:{repo_idx}")],
        [InlineKeyboardButton("🔙 Back",               callback_data="cmd_collabs")],
    ])

# ══ PROFILE ════════════════════════════════════════════════════════════════════
def profile_edit_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪪 Name",      callback_data="profile_edit:name"),
         InlineKeyboardButton("📝 Bio",       callback_data="profile_edit:bio")],
        [InlineKeyboardButton("📍 Location",  callback_data="profile_edit:location"),
         InlineKeyboardButton("🌐 Website",   callback_data="profile_edit:blog")],
        [InlineKeyboardButton("🐦 Twitter",   callback_data="profile_edit:twitter"),
         InlineKeyboardButton("🔙 Back",      callback_data="go_home")],
    ])
