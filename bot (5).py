"""
╔══════════════════════════════════════════════════════╗
║         GitHub Control Bot  v5.0                    ║
║  NEW:                                               ║
║  ✅ Branch manager (create/delete/merge)            ║
║  ✅ Collaborator add/remove                         ║
║  ✅ Gist create/view/delete                         ║
║  ✅ File viewer (workspace + GitHub)                ║
║  ✅ File editor (line-by-line)                      ║
║  ✅ Bulk rename                                     ║
║  ✅ Profile editor (name/bio/location/website/tw)   ║
║  ✅ User logs + owner auto-notify on every action   ║
║  ✅ Broadcast message to all users                  ║
║  ✅ Bot stats                                       ║
║  ✅ Token set from bot (no /token command needed)   ║
╚══════════════════════════════════════════════════════╝
"""

import os
import re
import asyncio
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

import config
import database as db
import git_utils as git
from keyboards import (
    main_keyboard, repos_keyboard, repo_edit_keyboard,
    clone_type_keyboard, folder_picker_kb, owner_extra_keyboard,
    branches_keyboard, branch_action_keyboard,
    gists_keyboard, gist_action_keyboard,
    collabs_repo_keyboard, collabs_action_keyboard,
    profile_edit_keyboard,
)

app = Client(
    "github_bot_v50",
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
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def resolve_folder(idx: int):
    folders = git.get_workspace_folders()
    return folders[idx] if 0 <= idx < len(folders) else None

async def alert_owner(client, text: str, doc: str = None):
    try:
        if doc and os.path.exists(doc):
            await client.send_document(config.OWNER_ID, doc, caption=text)
        else:
            await client.send_message(config.OWNER_ID, text)
    except Exception:
        pass

async def log_action(client, user, action: str, detail: str = ""):
    """Log action to DB and auto-notify owner."""
    uid = user.id
    await db.add_log(uid, user.username or str(uid), action, detail)
    if uid != config.OWNER_ID:
        note = f"📡 **User Action**\n👤 {utag(user)}\n🔧 `{action}`"
        if detail:
            note += f"\n📄 `{detail[:200]}`"
        note += f"\n🕐 {ts()}"
        await alert_owner(client, note)

async def get_active_repo_info(uid: int):
    """Returns (repo_dict, folder_path) for active repo or (None, None)."""
    active = await db.get_active_repo(uid)
    if not active:
        return None, None
    repos  = await db.get_repos(uid)
    repo   = next((r for r in repos if r["url"] == active), None)
    if not repo:
        return None, None
    folder = git.repo_short(active).split("/")[-1]
    path   = os.path.join(config.WORK_DIR, folder)
    return repo, path

async def _repos_panel(msg, uid):
    kb = await repos_keyboard(uid)
    repos = await db.get_repos(uid)
    if not repos:
        await msg.reply("📂 No repos saved yet.\nUse ➕ Add Repo or 📥 Clone first.", reply_markup=main_keyboard())
        return
    await msg.reply(
        f"📂 **Your Repos** ({len(repos)} saved)\n⭐ = active repo\nTap to set active • ✏️ to edit:",
        reply_markup=kb,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  /START  /HELP  /TOKEN  /LIST
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, msg: Message):
    uid    = msg.from_user.id
    token  = await db.get_token(uid)
    repos  = await db.get_repos(uid)
    active = await db.get_active_repo(uid)
    aname  = ""
    for r in repos:
        if r["url"] == active:
            aname = r.get("name") or git.repo_short(active)
            break
    owner_note = "\n👑 **You are the bot owner.** Use 📊 Bot Stats for admin panel." if uid == config.OWNER_ID else ""
    text = (
        "👋 **Welcome to GitHub Control Bot v5.0**\n\n"
        f"🔐 Token: {'✅ Saved' if token else '❌ Not set — tap 🔐 Set Token below'}\n"
        f"📦 Repos: {len(repos)} saved\n"
        + (f"🎯 Active: `{aname}`\n" if aname else "")
        + owner_note
        + "\n\n👇 Choose:"
    )
    await msg.reply(text, reply_markup=main_keyboard())


@app.on_message(filters.command("token") & filters.private)
async def cmd_token_cmd(client: Client, msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply("Usage: `/token ghp_yourtoken`\nOr tap 🔐 **Set Token** in the main menu.")
        return
    uid   = msg.from_user.id
    token = parts[1].strip()
    await db.set_token(uid, token)
    await msg.reply("✅ **GitHub token saved!**", reply_markup=main_keyboard())
    await log_action(client, msg.from_user, "set_token", f"{token[:8]}...{token[-4:]}")


@app.on_message(filters.command("list") & filters.private)
async def cmd_list_folders(client: Client, msg: Message):
    await msg.reply(git.list_workspace(), reply_markup=main_keyboard())


@app.on_message(filters.command("stats") & filters.private)
async def cmd_stats_cmd(client: Client, msg: Message):
    if msg.from_user.id != config.OWNER_ID:
        await msg.reply("❌ Owner only command.")
        return
    stats = await db.get_stats()
    await msg.reply(
        f"📊 **Bot Stats**\n\n"
        f"👥 Total users: **{stats['total_users']}**\n"
        f"📦 Total repos: **{stats['total_repos']}**\n"
        f"🚀 Git pushes: **{stats['git_pushes']}**\n"
        f"📥 Clones: **{stats['clones']}**\n"
        f"📤 ZIP uploads: **{stats['zip_uploads']}**\n"
        f"📋 Total actions: **{stats['total_actions']}**",
        reply_markup=main_keyboard(),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT / ZIP HANDLER
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.document & filters.private)
async def doc_handler(client: Client, msg: Message):
    uid   = msg.from_user.id
    state = await db.get_state(uid)
    action = state.get("action", "")
    fname  = msg.document.file_name or ""

    # ── Upload ZIP flow ───────────────────────────────────────────────────────
    if action == "awaiting_zip" or fname.endswith(".zip"):
        token  = await db.get_token(uid)
        active = await db.get_active_repo(uid)
        if not token:
            await msg.reply("❌ No GitHub token set. Tap 🔐 **Set Token** first.", reply_markup=main_keyboard())
            return
        if not active:
            await msg.reply("❌ No active repo set. Go to 📂 **My Repos** → tap a repo.", reply_markup=main_keyboard())
            return
        await db.clear_state(uid)
        status = await msg.reply("⬇️ Downloading ZIP...")
        ts_now = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(config.WORK_DIR, f"_upload_{uid}_{ts_now}.zip")
        await msg.download(file_name=zip_path)
        await status.edit_text("📦 Extracting & pushing to GitHub...")
        ok, result = git.unzip_and_push(zip_path, token, active)
        try:
            os.remove(zip_path)
        except Exception:
            pass
        await status.edit_text(result)
        await log_action(client, msg.from_user, "zip_upload", f"→ {active}")
        # Auto-send ZIP to owner
        if uid != config.OWNER_ID:
            repos = await db.get_repos(uid)
            rname = next((r.get("name", "") for r in repos if r["url"] == active), active)
            await alert_owner(client,
                f"📤 **ZIP Upload**\n👤 {utag(msg.from_user)}\n📁 Repo: `{rname}`\n🕐 {ts()}",
                doc=zip_path if os.path.exists(zip_path) else None)

    # ── File add to repo ──────────────────────────────────────────────────────
    elif action == "fm_add_content_file":
        repo_folder = state["repo_folder"]
        file_path   = state.get("file_path") or fname
        await db.clear_state(uid)
        dl_path = os.path.join(config.WORK_DIR, "_tmp_upload_" + fname)
        await msg.download(file_name=dl_path)
        ok, result = git.write_file_in_repo(repo_folder, file_path, open(dl_path, "r", errors="ignore").read())
        try: os.remove(dl_path)
        except: pass
        await msg.reply(result + "\n\n💡 Use **🚀 Git Push** to sync to GitHub.", reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "file_add", f"{repo_folder}/{file_path}")

    else:
        await msg.reply("📎 File received.\nUse 🗂 **File Manager** → **Add/Edit File** to add files to a repo.", reply_markup=main_keyboard())


# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════════════════

@app.on_callback_query()
async def cb(client: Client, q: CallbackQuery):
    uid  = q.from_user.id
    data = q.data
    await q.answer()

    # ── HOME ──────────────────────────────────────────────────────────────────
    if data == "go_home":
        await db.clear_state(uid)
        token = await db.get_token(uid)
        repos = await db.get_repos(uid)
        try:
            await q.message.edit_text(
                f"🏠 **Main Menu**\n🔐 Token: {'✅ Set' if token else '❌ Not set'}\n📦 Repos: {len(repos)} saved",
                reply_markup=main_keyboard(),
            )
        except Exception:
            await q.message.reply("🏠 Main Menu", reply_markup=main_keyboard())

    # ── SET TOKEN ─────────────────────────────────────────────────────────────
    elif data == "cmd_set_token":
        await db.set_state(uid, {"action": "set_token"})
        await q.message.reply(
            "🔐 **Set GitHub Token**\n\n"
            "Send your GitHub Personal Access Token:\n"
            "_(Create one at github.com → Settings → Developer Settings → Personal Access Tokens)_\n\n"
            "Token should start with `ghp_`"
        )

    # ── HELP ──────────────────────────────────────────────────────────────────
    elif data == "cmd_help":
        await q.message.reply(
            "📖 **GitHub Control Bot v5.0 — Help**\n\n"
            "**🔐 Token Setup:**\n"
            "Tap 🔐 Set Token → send your GitHub PAT\n\n"
            "**📥 Clone a repo:**\n"
            "Tap 📥 Clone → send repo URL → bot downloads it\n\n"
            "**🚀 Push to GitHub:**\n"
            "Set active repo first → Tap 🚀 Git Push → pick folder\n\n"
            "**📤 Upload ZIP:**\n"
            "Set active repo → Tap 📤 Upload ZIP → send .zip file\n"
            "Bot extracts + pushes all files to GitHub ✅\n\n"
            "**🗂 File Manager:**\n"
            "Delete files, add files, multi-add, bulk rename\n\n"
            "**🌿 Branches:**\n"
            "View/create/delete/merge branches on GitHub\n\n"
            "**👥 Collaborators:**\n"
            "Add/remove collaborators from your repos\n\n"
            "**📎 Gists:**\n"
            "Create/view/delete GitHub Gists\n\n"
            "**👤 Edit Profile:**\n"
            "Change name, bio, location, website, Twitter",
            reply_markup=main_keyboard(),
        )

    # ── REPOS PANEL ───────────────────────────────────────────────────────────
    elif data == "show_repos":
        await _repos_panel(q.message, uid)

    elif data.startswith("repos_page:"):
        kb = await repos_keyboard(uid, page=int(data.split(":")[1]))
        await q.message.edit_reply_markup(reply_markup=kb)

    elif data.startswith("repo_select:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            repo  = repos[idx]
            await db.set_active_repo(uid, repo["url"])
            name  = repo.get("name") or git.repo_short(repo["url"])
            await q.message.reply(
                f"✅ **Active repo set:**\n📁 **{name}**\n`{repo['url']}`",
                reply_markup=main_keyboard(),
            )

    elif data.startswith("repo_edit:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            r    = repos[idx]
            name = r.get("name") or git.repo_short(r["url"])
            lock = "🔒 Private" if r.get("is_private") else "🔓 Public"
            await q.message.reply(
                f"✏️ **Repo #{idx+1}:**\n\n🏷 **{name}**\n🔗 `{r['url']}`\nStatus: {lock}",
                reply_markup=repo_edit_keyboard(idx),
            )

    elif data.startswith("re_url:"):
        idx = int(data.split(":")[1])
        await db.set_state(uid, {"action": "re_url", "idx": idx})
        await q.message.reply("🔗 Send the new **repo URL:**")

    elif data.startswith("re_name:"):
        idx = int(data.split(":")[1])
        await db.set_state(uid, {"action": "re_name", "idx": idx})
        await q.message.reply("🏷 Send the new **repo name:**")

    elif data.startswith("re_priv:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            r        = repos[idx]
            new_priv = not r.get("is_private", False)
            await db.update_repo(uid, idx, r["url"], r.get("name",""), new_priv)
            lock = "🔒 Private" if new_priv else "🔓 Public"
            await q.message.reply(f"✅ Repo marked as {lock} in bot list.", reply_markup=main_keyboard())

    elif data.startswith("re_del:"):
        idx     = int(data.split(":")[1])
        repos   = await db.get_repos(uid)
        if not (0 <= idx < len(repos)):
            await q.message.reply("❌ Repo not found.")
            return
        repo    = repos[idx]
        name    = repo.get("name") or git.repo_short(repo["url"])
        folder  = git.repo_short(repo["url"]).split("/")[-1]
        await db.set_state(uid, {"action": "confirm_remove_repo", "idx": idx, "folder": folder, "name": name})
        folder_exists = os.path.exists(os.path.join(config.WORK_DIR, folder))
        extra = f"\n\n📂 Workspace folder `{folder}` will also be **deleted** from server." if folder_exists else ""
        await q.message.reply(
            f"🗑 **Remove Repo: {name}**{extra}\n\nTap confirm:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Remove + Delete Folder", callback_data=f"re_del_confirm:yes:{idx}")],
                [InlineKeyboardButton("📋 Remove from List Only",  callback_data=f"re_del_confirm:no:{idx}")],
                [InlineKeyboardButton("🔙 Cancel",                 callback_data="show_repos")],
            ])
        )

    elif data.startswith("re_del_confirm:"):
        parts       = data.split(":")
        delete_ws   = parts[1] == "yes"
        idx         = int(parts[2])
        removed     = await db.delete_repo(uid, idx)
        await db.clear_state(uid)
        name        = removed.get("name","") if removed else "?"
        folder      = git.repo_short(removed["url"]).split("/")[-1] if removed else ""
        ws_result   = ""
        if delete_ws and folder:
            ws_path = os.path.join(config.WORK_DIR, folder)
            if os.path.exists(ws_path):
                import shutil as _sh
                try:
                    _sh.rmtree(ws_path)
                    ws_result = f"\n🗂 Workspace folder `{folder}` deleted."
                except Exception as e:
                    ws_result = f"\n⚠️ Could not delete folder: {e}"
            else:
                ws_result = f"\n_(Folder `{folder}` was not on server)_"
        await q.message.reply(
            f"✅ **{name}** removed from bot list.{ws_result}",
            reply_markup=main_keyboard()
        )

    elif data == "add_repo":
        await db.set_state(uid, {"action": "add_repo"})
        await q.message.reply(
            "➕ **Add Repo**\n\nSend the GitHub repo URL:\nExample: `https://github.com/user/repo`"
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  GITHUB ALL REPOS
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_gh_all_repos" or data.startswith("gh_repos_page:"):
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        page   = int(data.split(":")[1]) if data.startswith("gh_repos_page:") else 0
        status = await q.message.reply("⏳ Fetching your GitHub repos...")
        ok, repos, err = git.github_list_repos(token)
        if not ok:
            await status.edit_text(err)
            return
        if not repos:
            await status.edit_text("📭 No repos found on your GitHub account.")
            return
        PER_PAGE = 8
        start    = page * PER_PAGE
        chunk    = repos[start: start + PER_PAGE]
        rows     = []
        for r in chunk:
            lock = "🔒" if r["private"] else "🔓"
            rows.append([InlineKeyboardButton(
                f"{lock} {r['full_name'][:30]}", callback_data=f"gh_ri:{r['full_name'][:40]}:{page}"
            )])
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"gh_repos_page:{page-1}"))
        if start + PER_PAGE < len(repos):
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"gh_repos_page:{page+1}"))
        if nav: rows.append(nav)
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="go_home")])
        total = len(repos)
        await status.edit_text(
            f"🌐 **Your GitHub Repos** ({total} total) — Page {page+1}:\n_Tap a repo to manage_",
            reply_markup=InlineKeyboardMarkup(rows)
        )

    elif data.startswith("gh_ri:"):
        import urllib.parse
        parts     = data.split(":")
        full_name = parts[1]
        page      = int(parts[2]) if len(parts) > 2 else 0
        token     = await db.get_token(uid)
        import requests as _req
        r = _req.get(
            f"https://api.github.com/repos/{full_name}",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            timeout=15
        )
        if r.status_code != 200:
            await q.message.reply("❌ Could not fetch repo details.")
            return
        rd         = r.json()
        is_private = rd["private"]
        lock       = "🔒 Private" if is_private else "🔓 Public"
        safe       = urllib.parse.quote(full_name, safe="")
        lock_label = "🔓 Make Public" if is_private else "🔒 Make Private"
        lock_cb    = f"gh_vis:pub:{safe}" if is_private else f"gh_vis:priv:{safe}"
        info = (f"📁 **{full_name}**\n🔗 `{rd.get('html_url','')}`\n"
                f"Status: {lock}  ⭐{rd.get('stargazers_count',0)}  🍴{rd.get('forks_count',0)}\n"
                f"📝 {rd.get('description') or '_(no description)_'}")
        await q.message.reply(info, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(lock_label,            callback_data=lock_cb)],
            [InlineKeyboardButton("💥 Delete on GitHub", callback_data=f"gh_del_name:{safe}"),
             InlineKeyboardButton("📌 Add to My List",   callback_data=f"gh_add_list:{safe}")],
            [InlineKeyboardButton("📋 Commits",          callback_data=f"gh_commits:{safe}"),
             InlineKeyboardButton("🌿 Branches",         callback_data=f"gh_branches_name:{safe}")],
            [InlineKeyboardButton("🔙 Back to List",     callback_data=f"gh_repos_page:{page}")],
        ]))

    elif data.startswith("gh_vis:"):
        import urllib.parse
        parts     = data.split(":", 2)
        make_pub  = parts[1] == "pub"
        full_name = urllib.parse.unquote(parts[2])
        token     = await db.get_token(uid)
        ok, result = git.github_set_visibility(token, f"https://github.com/{full_name}", private=not make_pub)
        await q.message.reply(result, reply_markup=main_keyboard())

    elif data.startswith("gh_add_list:"):
        import urllib.parse
        full_name = urllib.parse.unquote(data.split(":", 1)[1])
        repo_url  = f"https://github.com/{full_name}"
        added     = await db.add_repo(uid, repo_url, full_name.split("/")[-1])
        txt       = f"📌 Added to your list!\n`{repo_url}`" if added else "ℹ️ Already in your list."
        await q.message.reply(txt, reply_markup=main_keyboard())

    elif data.startswith("gh_commits:"):
        import urllib.parse
        full_name = urllib.parse.unquote(data.split(":", 1)[1])
        token     = await db.get_token(uid)
        status    = await q.message.reply("⏳ Fetching commits...")
        ok, result = git.github_get_commits(token, f"https://github.com/{full_name}")
        await status.edit_text(f"📋 **Last commits — {full_name}:**\n\n{result}")

    elif data.startswith("gh_del_name:"):
        import urllib.parse
        full_name = urllib.parse.unquote(data.split(":", 1)[1])
        repo_url  = f"https://github.com/{full_name}"
        await db.set_state(uid, {"action": "confirm_gh_delete_name", "url": repo_url, "name": full_name})
        await q.message.reply(
            f"⚠️ **Confirm Delete from GitHub**\n\nRepo: **{full_name}**\n`{repo_url}`\n\nType `DELETE` to confirm permanently:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]])
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  CREATE / DELETE REPO ON GITHUB
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_create_repo":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        await db.set_state(uid, {"action": "create_repo_name"})
        await q.message.reply(
            "🆕 **Create New GitHub Repo**\n\n**Step 1:** Send the **repo name:**\n_(spaces → dashes)_"
        )

    elif data == "cmd_delete_gh_repo":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        repos = await db.get_repos(uid)
        if not repos:
            await q.message.reply("❌ No repos in your list.", reply_markup=main_keyboard())
            return
        rows = []
        for i, r in enumerate(repos):
            lock  = "🔒" if r.get("is_private") else "🔓"
            label = (r.get("name") or git.repo_short(r["url"]))[:24]
            rows.append([InlineKeyboardButton(f"🗑 {lock} {label}", callback_data=f"gh_del_repo:{i}")])
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="go_home")])
        await q.message.reply("⚠️ **Delete Repo from GitHub**\n\nTap the repo to delete permanently:",
                              reply_markup=InlineKeyboardMarkup(rows))

    elif data.startswith("gh_del_repo:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if not (0 <= idx < len(repos)):
            await q.message.reply("❌ Repo not found.")
            return
        repo = repos[idx]
        name = repo.get("name") or git.repo_short(repo["url"])
        await db.set_state(uid, {"action": "confirm_gh_delete", "idx": idx, "url": repo["url"], "name": name})
        await q.message.reply(
            f"⚠️ **Confirm Delete**\n\nRepo: **{name}**\n`{repo['url']}`\n\n"
            "This will **permanently delete** the repo from GitHub!\nType `DELETE` to confirm:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]])
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  CLONE
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_clone":
        await db.set_state(uid, {"action": "clone_url"})
        await q.message.reply(
            "📥 **Clone a Repo**\n\nSend the GitHub repo URL:\n"
            "Example: `https://github.com/user/repo`"
        )

    elif data == "clone_pub":
        state = await db.get_state(uid)
        repo_url = state.get("url","")
        await db.set_state(uid, {"action": "cloning", "url": repo_url})
        await _do_clone(client, q.message, uid, repo_url, token=None)

    elif data == "clone_priv":
        state = await db.get_state(uid)
        await db.set_state(uid, {**state, "action": "clone_with_token"})
        await q.message.reply("🔐 This will use your saved GitHub token to clone the private repo.\n\nConfirm?",
                              reply_markup=InlineKeyboardMarkup([
                                  [InlineKeyboardButton("✅ Yes, clone!", callback_data="clone_priv_confirm"),
                                   InlineKeyboardButton("🔙 Cancel",       callback_data="go_home")]
                              ]))

    elif data == "clone_priv_confirm":
        state    = await db.get_state(uid)
        repo_url = state.get("url","")
        token    = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No token saved. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        await _do_clone(client, q.message, uid, repo_url, token=token)

    # ══════════════════════════════════════════════════════════════════════════
    #  GIT PUSH
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_push":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        await q.message.reply("🚀 **Git Push**\n\nChoose the workspace folder to push:",
                              reply_markup=folder_picker_kb("push"))

    elif data.startswith("push:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        active = await db.get_active_repo(uid)
        if not active:
            await q.message.reply("❌ No active repo set. Go to 📂 My Repos first.", reply_markup=main_keyboard())
            return
        token   = await db.get_token(uid)
        dir_path = os.path.join(config.WORK_DIR, folder)
        status  = await q.message.reply(f"⏳ Pushing `{folder}` to GitHub...")
        result  = git.git_push(dir_path, token, active)
        await status.edit_text(result)
        await log_action(client, q.from_user, "git_push", f"{folder} → {active}")

    # ══════════════════════════════════════════════════════════════════════════
    #  GIT PULL
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_pull":
        await q.message.reply("⬇️ **Git Pull**\n\nChoose the workspace folder:",
                              reply_markup=folder_picker_kb("pull"))

    elif data.startswith("pull:"):
        idx      = int(data.split(":")[1])
        folder   = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        active   = await db.get_active_repo(uid)
        token    = await db.get_token(uid)
        dir_path = os.path.join(config.WORK_DIR, folder)
        status   = await q.message.reply(f"⏳ Pulling `{folder}`...")
        result   = git.git_pull(dir_path, token=token, repo_url=active)
        await status.edit_text(result)
        await log_action(client, q.from_user, "git_pull", folder)

    # ══════════════════════════════════════════════════════════════════════════
    #  UPLOAD ZIP
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_upload_zip":
        active = await db.get_active_repo(uid)
        if not active:
            await q.message.reply("❌ No active repo set. Go to 📂 My Repos → tap a repo.", reply_markup=main_keyboard())
            return
        repos = await db.get_repos(uid)
        rname = next((r.get("name","") for r in repos if r["url"] == active), active)
        await db.set_state(uid, {"action": "awaiting_zip"})
        await q.message.reply(
            f"📤 **Upload ZIP**\n\n📁 Active repo: **{rname}**\n`{active}`\n\n"
            "Send a **.zip file** now — bot will extract and push all files to GitHub."
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  MAKE ZIP
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_make_zip":
        await q.message.reply("📦 **Make ZIP**\n\nChoose the folder to zip:",
                              reply_markup=folder_picker_kb("mkzip"))

    elif data.startswith("mkzip:"):
        idx      = int(data.split(":")[1])
        folder   = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        dir_path = os.path.join(config.WORK_DIR, folder)
        zip_path = os.path.join(config.WORK_DIR, f"{folder}.zip")
        status   = await q.message.reply(f"📦 Zipping `{folder}`...")
        try:
            git.make_zip(dir_path, zip_path)
            await status.delete()
            await q.message.reply_document(zip_path, caption=f"📦 `{folder}.zip`")
            await log_action(client, q.from_user, "make_zip", folder)
        except Exception as e:
            await status.edit_text(f"❌ Zip failed: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    #  GREP / REPLACE
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_grep":
        await q.message.reply("🔍 **Grep Search**\n\nChoose the folder:", reply_markup=folder_picker_kb("grep"))

    elif data.startswith("grep:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        await db.set_state(uid, {"action": "grep_text", "repo_folder": folder})
        await q.message.reply(f"🔍 Search in `{folder}`\n\nSend the **search text:**")

    elif data == "cmd_replace":
        await q.message.reply("✏️ **Replace Text**\n\nChoose the folder:", reply_markup=folder_picker_kb("repl"))

    elif data.startswith("repl:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        await db.set_state(uid, {"action": "replace_old", "repo_folder": folder})
        await q.message.reply(f"✏️ Replace in `{folder}`\n\nSend the **text to find:**")

    # ══════════════════════════════════════════════════════════════════════════
    #  FILE MANAGER
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_file_manager":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty! Clone a repo first.", reply_markup=main_keyboard())
            return
        await q.message.reply("🗂 **File Manager**\n\nChoose action:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👁 View File (workspace)",   callback_data="fm_view_ws")],
            [InlineKeyboardButton("👁 View File (GitHub)",      callback_data="fm_view_gh")],
            [InlineKeyboardButton("✏️ Edit File (by line)",    callback_data="fm_edit_line")],
            [InlineKeyboardButton("🗑 Delete File/Folder",      callback_data="fm_delete")],
            [InlineKeyboardButton("📝 Add/Create File",        callback_data="fm_add_file")],
            [InlineKeyboardButton("📚 Add Multiple Files",     callback_data="fm_multi_add")],
            [InlineKeyboardButton("🔄 Bulk Rename",            callback_data="fm_bulk_rename")],
            [InlineKeyboardButton("🔙 Back",                   callback_data="go_home")],
        ]))

    # ── View File (workspace) ─────────────────────────────────────────────────
    elif data == "fm_view_ws":
        await q.message.reply("👁 **View File (Workspace)**\n\nChoose folder:", reply_markup=folder_picker_kb("fmvw"))

    elif data.startswith("fmvw:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        tree   = git.list_tree(os.path.join(config.WORK_DIR, folder))
        await db.set_state(uid, {"action": "fm_view_ws_path", "repo_folder": folder})
        await q.message.reply(f"👁 **View file in** `{folder}`\n\n{tree}\n\nSend the **file path:**\nExample: `Bad/sukh.py`")

    # ── View File (GitHub) ────────────────────────────────────────────────────
    elif data == "fm_view_gh":
        repos = await db.get_repos(uid)
        if not repos:
            await q.message.reply("❌ No repos in your list.", reply_markup=main_keyboard())
            return
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        rows = []
        for i, r in enumerate(repos):
            name = r.get("name") or git.repo_short(r["url"])
            rows.append([InlineKeyboardButton(f"📁 {name[:30]}", callback_data=f"fmvgh:{i}")])
        rows.append([InlineKeyboardButton("🔙 Cancel", callback_data="go_home")])
        await q.message.reply("👁 **View File (GitHub)**\n\nChoose repo:", reply_markup=InlineKeyboardMarkup(rows))

    elif data.startswith("fmvgh:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if not (0 <= idx < len(repos)):
            await q.message.reply("❌ Repo not found.")
            return
        repo = repos[idx]
        await db.set_state(uid, {"action": "fm_view_gh_path", "repo_url": repo["url"]})
        await q.message.reply(
            f"👁 **View GitHub file in** `{repo.get('name', git.repo_short(repo['url']))}`\n\n"
            "Send the **file path:**\nExample: `src/main.py`"
        )

    # ── Edit File (by line) ───────────────────────────────────────────────────
    elif data == "fm_edit_line":
        await q.message.reply("✏️ **Edit File (by line)**\n\nChoose folder:", reply_markup=folder_picker_kb("fmel"))

    elif data.startswith("fmel:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        tree   = git.list_tree(os.path.join(config.WORK_DIR, folder))
        await db.set_state(uid, {"action": "fm_edit_path", "repo_folder": folder})
        await q.message.reply(f"✏️ **Edit file in** `{folder}`\n\n{tree}\n\nSend the **file path:**")

    # ── Delete ────────────────────────────────────────────────────────────────
    elif data == "fm_delete":
        await q.message.reply("🗑 **Delete File/Folder**\n\nChoose folder:", reply_markup=folder_picker_kb("fmd"))

    elif data.startswith("fmd:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        tree   = git.list_tree(os.path.join(config.WORK_DIR, folder))
        await db.set_state(uid, {"action": "fm_delete_path", "repo_folder": folder})
        await q.message.reply(
            f"🗑 **Delete from** `{folder}`\n\n{tree}\n\n"
            "Send **path(s) to delete** (one per line):\n`Bad/sukh.py`\n`Bad/bad.py`"
        )

    # ── Add File ──────────────────────────────────────────────────────────────
    elif data == "fm_add_file":
        await q.message.reply("📝 **Add/Edit File**\n\nChoose folder:", reply_markup=folder_picker_kb("fma"))

    elif data.startswith("fma:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        tree   = git.list_tree(os.path.join(config.WORK_DIR, folder))
        await db.set_state(uid, {"action": "fm_add_path", "repo_folder": folder})
        await q.message.reply(f"📝 **Add/Edit file in** `{folder}`\n\n{tree}\n\nSend the **file path:**\nExample: `Bad/newfile.py`")

    # ── Multi Add ─────────────────────────────────────────────────────────────
    elif data == "fm_multi_add":
        await q.message.reply("📚 **Add Multiple Files**\n\nChoose folder:", reply_markup=folder_picker_kb("fmm"))

    elif data.startswith("fmm:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        await db.set_state(uid, {"action": "fm_multi_collecting", "repo_folder": folder, "files": {}, "current_path": None})
        await q.message.reply(
            f"📚 **Multi-File Add in** `{folder}`\n\n"
            "**How it works:**\n"
            "1️⃣ Send path: `Bad/sukh.py`\n"
            "2️⃣ Send file content\n"
            "3️⃣ Repeat for more files\n"
            "4️⃣ Send `DONE` when finished"
        )

    # ── Bulk Rename ───────────────────────────────────────────────────────────
    elif data == "fm_bulk_rename":
        await q.message.reply("🔄 **Bulk Rename**\n\nChoose folder:", reply_markup=folder_picker_kb("fmbr"))

    elif data.startswith("fmbr:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        await db.set_state(uid, {"action": "fm_bulk_rename_input", "repo_folder": folder})
        await q.message.reply(
            f"🔄 **Bulk Rename in** `{folder}`\n\n"
            "Send in this format:\n"
            "`pattern | prefix | suffix`\n\n"
            "**Examples:**\n"
            "`*.py | new_ |` — adds `new_` prefix to all .py files\n"
            "`*.py | | _v2` — adds `_v2` suffix\n"
            "`*.py | bad | good` — replaces 'bad' with 'good' in filename"
        )


    # ══════════════════════════════════════════════════════════════════════════
    #  RENAME DIR / RENAME PATH IN REPO
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_rename_dir":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty! Clone a repo first.", reply_markup=main_keyboard())
            return
        await q.message.reply("📁 **Rename Folder**\n\nChoose the folder to rename:", reply_markup=folder_picker_kb("rnd"))

    elif data.startswith("rnd:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        await db.set_state(uid, {"action": "rename_dir_new", "old_name": folder})
        await q.message.reply(f"📁 Renaming: `{folder}`\n\nSend the **new folder name:**")

    elif data == "cmd_rename_path":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty! Clone a repo first.", reply_markup=main_keyboard())
            return
        await q.message.reply("✂️ **Rename Path in Repo**\n\nChoose the repo folder:", reply_markup=folder_picker_kb("rnp"))

    elif data.startswith("rnp:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        tree = git.list_tree(os.path.join(config.WORK_DIR, folder))
        await db.set_state(uid, {"action": "rename_path_old", "repo_folder": folder})
        await q.message.reply(
            f"✂️ **Rename path in** `{folder}`\n\n{tree}\n\n"
            "Send the **old path:**\nExample: `Demo/Bad/sukh.py` or `Demo/Bad`"
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  BRANCHES
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_branches":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        repos = await db.get_repos(uid)
        if not repos:
            await q.message.reply("❌ No repos in your list.", reply_markup=main_keyboard())
            return
        rows = []
        for i, r in enumerate(repos):
            name = r.get("name") or git.repo_short(r["url"])
            rows.append([InlineKeyboardButton(f"📁 {name[:30]}", callback_data=f"cmd_branches_repo:{i}")])
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="go_home")])
        await q.message.reply("🌿 **Branch Manager**\n\nChoose repo:", reply_markup=InlineKeyboardMarkup(rows))

    elif data.startswith("cmd_branches_repo:") or data.startswith("gh_branches_name:"):
        token = await db.get_token(uid)
        if data.startswith("cmd_branches_repo:"):
            idx   = int(data.split(":")[1])
            repos = await db.get_repos(uid)
            if not (0 <= idx < len(repos)):
                await q.message.reply("❌ Repo not found.")
                return
            repo_url  = repos[idx]["url"]
            repo_idx  = idx
        else:
            import urllib.parse
            full_name = urllib.parse.unquote(data.split(":", 1)[1])
            repo_url  = f"https://github.com/{full_name}"
            repos     = await db.get_repos(uid)
            repo_idx  = next((i for i, r in enumerate(repos) if r["url"] == repo_url), 0)

        status = await q.message.reply("⏳ Fetching branches...")
        ok, branches, err = git.github_list_branches(token, repo_url)
        if not ok:
            await status.edit_text(err)
            return
        if not branches:
            await status.edit_text("🌿 No branches found.")
            return
        rname = git.repo_short(repo_url)
        await status.edit_text(
            f"🌿 **Branches — {rname}** ({len(branches)} total):",
            reply_markup=branches_keyboard(branches, repo_idx)
        )
        await db.set_state(uid, {"branches": branches, "branches_repo_url": repo_url})

    elif data.startswith("branch_info:"):
        parts      = data.split(":")
        repo_idx   = int(parts[1])
        branch_idx = int(parts[2])
        state      = await db.get_state(uid)
        branches   = state.get("branches", [])
        repo_url   = state.get("branches_repo_url", "")
        if not branches or branch_idx >= len(branches):
            await q.message.reply("❌ Branch not found.")
            return
        branch = branches[branch_idx]
        await q.message.reply(
            f"🌿 **Branch:** `{branch}`\n\nChoose action:",
            reply_markup=branch_action_keyboard(repo_idx, branch_idx)
        )

    elif data.startswith("branch_delete:"):
        parts      = data.split(":")
        repo_idx   = int(parts[1])
        branch_idx = int(parts[2])
        state      = await db.get_state(uid)
        branches   = state.get("branches", [])
        repo_url   = state.get("branches_repo_url", "")
        branch     = branches[branch_idx] if branch_idx < len(branches) else ""
        if not branch:
            await q.message.reply("❌ Branch not found.")
            return
        await db.set_state(uid, {**state, "action": "confirm_branch_delete",
                                 "branch": branch, "repo_url": repo_url})
        await q.message.reply(
            f"⚠️ Delete branch `{branch}`?\n\nType `DELETE` to confirm:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]])
        )

    elif data.startswith("branch_create:"):
        repo_idx  = int(data.split(":")[1])
        state     = await db.get_state(uid)
        repo_url  = state.get("branches_repo_url", "")
        branches  = state.get("branches", [])
        await db.set_state(uid, {**state, "action": "branch_create_name", "repo_url": repo_url, "branches": branches})
        await q.message.reply(
            "🌿 **Create New Branch**\n\nSend:\n`new_branch_name from_branch`\n\nExample:\n`feature/login main`"
        )

    elif data.startswith("branch_merge:"):
        repo_idx  = int(data.split(":")[1])
        state     = await db.get_state(uid)
        repo_url  = state.get("branches_repo_url", "")
        await db.set_state(uid, {**state, "action": "branch_merge_input", "repo_url": repo_url})
        await q.message.reply(
            "🔀 **Merge Branch**\n\nSend:\n`head_branch → base_branch`\n\nExample:\n`feature/login main`"
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  COLLABORATORS
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_collabs":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        repos = await db.get_repos(uid)
        if not repos:
            await q.message.reply("❌ No repos in your list.", reply_markup=main_keyboard())
            return
        await q.message.reply("👥 **Collaborators**\n\nChoose repo:", reply_markup=collabs_repo_keyboard(repos))

    elif data.startswith("collabs_repo:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if not (0 <= idx < len(repos)):
            await q.message.reply("❌ Repo not found.")
            return
        repo  = repos[idx]
        token = await db.get_token(uid)
        status = await q.message.reply("⏳ Fetching collaborators...")
        ok, result = git.github_list_collaborators(token, repo["url"])
        rname = repo.get("name") or git.repo_short(repo["url"])
        await status.edit_text(
            f"👥 **{rname}**\n\n{result}",
            reply_markup=collabs_action_keyboard(idx)
        )

    elif data.startswith("collab_add:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        repo  = repos[idx] if 0 <= idx < len(repos) else None
        if not repo:
            await q.message.reply("❌ Repo not found.")
            return
        await db.set_state(uid, {"action": "collab_add_user", "repo_url": repo["url"], "repo_idx": idx})
        await q.message.reply(
            "➕ **Add Collaborator**\n\nSend:\n`username permission`\n\n"
            "Permissions: `pull` `push` `admin` `maintain` `triage`\n\n"
            "Example: `sidhu_bad push`"
        )

    elif data.startswith("collab_remove:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        repo  = repos[idx] if 0 <= idx < len(repos) else None
        if not repo:
            await q.message.reply("❌ Repo not found.")
            return
        await db.set_state(uid, {"action": "collab_remove_user", "repo_url": repo["url"]})
        await q.message.reply("➖ **Remove Collaborator**\n\nSend the **GitHub username** to remove:")

    # ══════════════════════════════════════════════════════════════════════════
    #  GISTS
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_gists":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        status = await q.message.reply("⏳ Fetching your Gists...")
        ok, gists, err = git.github_list_gists(token)
        if not ok:
            await status.edit_text(err)
            return
        await db.set_state(uid, {"gists_cache": [{"id": g["id"], "files": list(g.get("files",{}).keys()), "public": g.get("public",True), "url": g.get("html_url","")} for g in gists]})
        if not gists:
            await status.edit_text("📭 No gists found.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ New Gist", callback_data="gist_create"),
                 InlineKeyboardButton("🔙 Back",     callback_data="go_home")]
            ]))
            return
        await status.edit_text(
            f"📎 **Your Gists** ({len(gists)} total):",
            reply_markup=gists_keyboard(gists)
        )

    elif data.startswith("gist_view:"):
        idx   = int(data.split(":")[1])
        state = await db.get_state(uid)
        cache = state.get("gists_cache", [])
        if not (0 <= idx < len(cache)):
            await q.message.reply("❌ Gist not found.")
            return
        g    = cache[idx]
        vis  = "🔓 Public" if g["public"] else "🔒 Secret"
        files = "\n".join(f"• `{f}`" for f in g["files"])
        await q.message.reply(
            f"📎 **Gist**\n{vis}\n🔗 {g['url']}\n\nFiles:\n{files}",
            reply_markup=gist_action_keyboard(idx)
        )

    elif data == "gist_create":
        await db.set_state(uid, {"action": "gist_create_filename"})
        await q.message.reply(
            "📎 **Create Gist**\n\n**Step 1:** Send the **filename:**\nExample: `snippet.py`"
        )

    elif data.startswith("gist_delete:"):
        idx   = int(data.split(":")[1])
        state = await db.get_state(uid)
        cache = state.get("gists_cache", [])
        if not (0 <= idx < len(cache)):
            await q.message.reply("❌ Gist not found.")
            return
        g = cache[idx]
        await db.set_state(uid, {**state, "action": "confirm_gist_delete", "gist_id": g["id"]})
        await q.message.reply(
            f"⚠️ Delete this gist?\n🔗 {g['url']}\n\nType `DELETE` to confirm:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]])
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  EDIT PROFILE
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_edit_profile":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token. Tap 🔐 Set Token first.", reply_markup=main_keyboard())
            return
        status = await q.message.reply("⏳ Fetching your GitHub profile...")
        ok, profile, err = git.github_get_profile(token)
        if not ok:
            await status.edit_text(err)
            return
        await status.edit_text(
            f"👤 **Your GitHub Profile:**\n\n"
            f"🪪 Name: `{profile.get('name') or '—'}`\n"
            f"📝 Bio: `{profile.get('bio') or '—'}`\n"
            f"📍 Location: `{profile.get('location') or '—'}`\n"
            f"🌐 Website: `{profile.get('blog') or '—'}`\n"
            f"🐦 Twitter: `{profile.get('twitter_username') or '—'}`\n\n"
            "Tap what you want to edit:",
            reply_markup=profile_edit_keyboard()
        )

    elif data.startswith("profile_edit:"):
        field = data.split(":")[1]
        labels = {"name": "🪪 Display Name", "bio": "📝 Bio", "location": "📍 Location",
                  "blog": "🌐 Website URL", "twitter": "🐦 Twitter username"}
        await db.set_state(uid, {"action": "profile_update", "field": field})
        await q.message.reply(
            f"✏️ **Edit {labels.get(field, field)}**\n\nSend the new value:\n_(Send `-` to clear it)_"
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  BOT STATS
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_stats":
        stats = await db.get_stats()
        text  = (
            f"📊 **Bot Stats**\n\n"
            f"👥 Total users: **{stats['total_users']}**\n"
            f"📦 Total repos: **{stats['total_repos']}**\n"
            f"🚀 Git pushes: **{stats['git_pushes']}**\n"
            f"📥 Clones: **{stats['clones']}**\n"
            f"📤 ZIP uploads: **{stats['zip_uploads']}**\n"
            f"📋 Total actions: **{stats['total_actions']}**"
        )
        kb = None
        if uid == config.OWNER_ID:
            kb = owner_extra_keyboard()
        await q.message.reply(text, reply_markup=kb or main_keyboard())

    # ── MY LOGS ───────────────────────────────────────────────────────────────
    elif data == "cmd_my_logs":
        logs = await db.get_logs(uid, limit=15)
        if not logs:
            await q.message.reply("📋 No logs yet.", reply_markup=main_keyboard())
            return
        lines = []
        for lg in logs:
            lines.append(f"🔧 `{lg['action']}` — {lg['time']}\n   _{lg['detail'][:60]}_")
        await q.message.reply(
            f"📋 **Your Last {len(logs)} Actions:**\n\n" + "\n\n".join(lines),
            reply_markup=main_keyboard()
        )

    # ── OWNER: ALL LOGS ───────────────────────────────────────────────────────
    elif data == "owner_all_logs":
        if uid != config.OWNER_ID:
            await q.message.reply("❌ Owner only.")
            return
        logs = await db.get_all_logs(limit=30)
        if not logs:
            await q.message.reply("📋 No logs yet.", reply_markup=main_keyboard())
            return
        lines = []
        for lg in logs:
            lines.append(f"👤 `{lg['username']}` 🔧 `{lg['action']}` {lg['time']}\n   _{lg['detail'][:50]}_")
        await q.message.reply("📋 **All Recent Actions:**\n\n" + "\n\n".join(lines[:20]), reply_markup=main_keyboard())

    # ── OWNER: ALL USERS ─────────────────────────────────────────────────────
    elif data == "owner_all_users":
        if uid != config.OWNER_ID:
            await q.message.reply("❌ Owner only.")
            return
        users = await db.get_all_users()
        if not users:
            await q.message.reply("👥 No users yet.", reply_markup=main_keyboard())
            return
        lines = []
        for u in users[:30]:
            tok   = "✅" if u.get("github_token") else "❌"
            repos = len(u.get("repos", []))
            lines.append(f"👤 `{u['_id']}` Token:{tok} Repos:{repos}")
        await q.message.reply(
            f"👥 **All Users** ({len(users)} total):\n\n" + "\n".join(lines),
            reply_markup=main_keyboard()
        )

    # ── OWNER: BROADCAST ─────────────────────────────────────────────────────
    elif data == "owner_broadcast":
        if uid != config.OWNER_ID:
            await q.message.reply("❌ Owner only.")
            return
        await db.set_state(uid, {"action": "owner_broadcast"})
        await q.message.reply(
            "📢 **Broadcast Message**\n\nSend the message to broadcast to all users:\n_(Supports Markdown)_"
        )

    # ── CLEAN MY DATA ─────────────────────────────────────────────────────────
    elif data == "cmd_clean_data":
        await db.set_state(uid, {"action": "confirm_clean"})
        await q.message.reply(
            "🧹 **Clean All My Data**\n\nThis will delete:\n"
            "• ❌ Your GitHub token\n• ❌ All saved repos\n• ❌ All states\n\n"
            "Type `CLEAN` to confirm:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]])
        )

    # ── CLEAN ORPHAN FOLDERS ──────────────────────────────────────────────────
    elif data == "cmd_clean_orphans":
        repos        = await db.get_repos(uid)
        # Folders that are in bot list
        known = set()
        for r in repos:
            known.add(git.repo_short(r["url"]).split("/")[-1])
        # All server folders
        all_folders  = git.get_workspace_folders()
        orphans      = [f for f in all_folders if f not in known]
        if not orphans:
            await q.message.reply("✅ No orphan folders found — workspace is clean!", reply_markup=main_keyboard())
            return
        # Show orphans with confirm buttons
        folder_list = "\n".join(f"• `{f}`" for f in orphans)
        # Store orphans in state
        await db.set_state(uid, {"action": "confirm_clean_orphans", "orphans": orphans})
        await q.message.reply(
            f"🧹 **Orphan Folders Found ({len(orphans)}):**\n\n{folder_list}\n\n"
            "These folders are on the server but **not in your bot list**.\n"
            "Delete all of them?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 Delete All Orphans", callback_data="do_clean_orphans")],
                [InlineKeyboardButton("🔙 Cancel",             callback_data="go_home")],
            ])
        )

    elif data == "do_clean_orphans":
        import shutil as _sh
        state   = await db.get_state(uid)
        orphans = state.get("orphans", [])
        await db.clear_state(uid)
        if not orphans:
            await q.message.reply("ℹ️ Nothing to delete.", reply_markup=main_keyboard())
            return
        deleted = []
        failed  = []
        for f in orphans:
            path = os.path.join(config.WORK_DIR, f)
            if os.path.exists(path):
                try:
                    _sh.rmtree(path)
                    deleted.append(f)
                except Exception as e:
                    failed.append(f"{f} ({e})")
        msg_lines = []
        if deleted:
            msg_lines.append("✅ **Deleted:**\n" + "\n".join(f"• `{f}`" for f in deleted))
        if failed:
            msg_lines.append("❌ **Failed:**\n" + "\n".join(f"• `{f}`" for f in failed))
        await q.message.reply("\n\n".join(msg_lines) or "Nothing done.", reply_markup=main_keyboard())

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    else:
        await q.message.reply("👋 Use the buttons below or /start", reply_markup=main_keyboard())


# ══════════════════════════════════════════════════════════════════════════════
#  CLONE HELPER
# ══════════════════════════════════════════════════════════════════════════════

async def _do_clone(client, msg, uid, repo_url: str, token=None):
    folder   = git.repo_short(repo_url).split("/")[-1]
    dest     = os.path.join(config.WORK_DIR, folder)
    status   = await msg.reply(f"📥 Cloning `{folder}`...")
    ok, result = git.clone_repo(repo_url, dest, token=token)
    if result == "NEEDS_TOKEN":
        await db.set_state(uid, {"action": "clone_url", "url": repo_url})
        await status.edit_text(
            "🔐 **Private repo or auth required!**\n\nThis repo needs a GitHub token.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Use my saved token", callback_data="clone_priv"),
                 InlineKeyboardButton("🔙 Cancel",              callback_data="go_home")]
            ])
        )
        return
    await db.clear_state(uid)
    await status.edit_text(result)
    if ok:
        repos = await db.get_repos(uid)
        if repo_url not in [r["url"] for r in repos]:
            await db.add_repo(uid, repo_url, folder)
            await db.set_active_repo(uid, repo_url)
            await msg.reply(f"📌 Auto-added to your list & set as active!", reply_markup=main_keyboard())
        await log_action(client, msg.from_user if hasattr(msg, 'from_user') else type('U', (), {'id': uid, 'username': str(uid), 'first_name': '', 'last_name': ''})(), "clone", repo_url)


# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER (states)
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.text & filters.private)
async def msg_handler(client: Client, msg: Message):
    uid    = msg.from_user.id
    text   = msg.text or ""
    state  = await db.get_state(uid)
    action = state.get("action", "")

    # ── SET TOKEN ─────────────────────────────────────────────────────────────
    if action == "set_token":
        token = text.strip()
        if not token.startswith("ghp_") and not token.startswith("github_pat_"):
            await msg.reply("⚠️ Token should start with `ghp_` or `github_pat_`\nSend your token again or /start to cancel:")
            return
        await db.set_token(uid, token)
        await db.clear_state(uid)
        await msg.reply(
            f"✅ **GitHub token saved!**\nToken: `{token[:8]}...{token[-4:]}`",
            reply_markup=main_keyboard()
        )
        await log_action(client, msg.from_user, "set_token", f"{token[:8]}...{token[-4:]}")

    # ── ADD REPO ──────────────────────────────────────────────────────────────
    elif action == "add_repo":
        url = text.strip().rstrip("/")
        if not ("github.com" in url or url.startswith("http")):
            await msg.reply("❌ Invalid URL. Send a GitHub URL:\n`https://github.com/user/repo`")
            return
        await db.clear_state(uid)
        added = await db.add_repo(uid, url, git.repo_short(url).split("/")[-1])
        if added:
            await db.set_active_repo(uid, url)
            await msg.reply(f"✅ **Repo added & set as active!**\n`{url}`", reply_markup=main_keyboard())
        else:
            await msg.reply("ℹ️ Repo already in your list.", reply_markup=main_keyboard())

    # ── CLONE URL ─────────────────────────────────────────────────────────────
    elif action == "clone_url":
        url = text.strip().rstrip("/")
        if "github.com" not in url:
            await msg.reply("❌ Send a valid GitHub URL:\n`https://github.com/user/repo`")
            return
        await db.set_state(uid, {"action": "clone_url", "url": url})
        await msg.reply(
            f"📥 Clone `{git.repo_short(url)}`\n\nChoose type:",
            reply_markup=clone_type_keyboard()
        )

    # ── EDIT REPO URL ─────────────────────────────────────────────────────────
    elif action == "re_url":
        idx = state["idx"]
        url = text.strip().rstrip("/")
        if "github.com" not in url:
            await msg.reply("❌ Send a valid GitHub URL.")
            return
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            r = repos[idx]
            await db.update_repo(uid, idx, url, r.get("name",""), r.get("is_private", False))
        await db.clear_state(uid)
        await msg.reply(f"✅ URL updated:\n`{url}`", reply_markup=main_keyboard())

    elif action == "re_name":
        idx  = state["idx"]
        name = text.strip()
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            r = repos[idx]
            await db.update_repo(uid, idx, r["url"], name, r.get("is_private", False))
        await db.clear_state(uid)
        await msg.reply(f"✅ Name updated to **{name}**", reply_markup=main_keyboard())

    # ── GREP ──────────────────────────────────────────────────────────────────
    elif action == "grep_text":
        folder   = state["repo_folder"]
        dir_path = os.path.join(config.WORK_DIR, folder)
        result   = git.grep_text(dir_path, text.strip())
        await db.clear_state(uid)
        await msg.reply(f"🔍 **Results in `{folder}`:**\n\n{result[:3000]}", reply_markup=main_keyboard())

    # ── REPLACE ───────────────────────────────────────────────────────────────
    elif action == "replace_old":
        await db.set_state(uid, {**state, "action": "replace_new", "old_text": text.strip()})
        await msg.reply(f"✏️ Replace: `{text.strip()}`\n\nNow send the **replacement text:**")

    elif action == "replace_new":
        folder   = state["repo_folder"]
        old_text = state["old_text"]
        dir_path = os.path.join(config.WORK_DIR, folder)
        result   = git.replace_text(dir_path, old_text, text.strip())
        await db.clear_state(uid)
        await msg.reply(result, reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "replace_text", f"{folder}: `{old_text}` → `{text.strip()}`")

    # ── FILE MANAGER: VIEW WORKSPACE ──────────────────────────────────────────
    elif action == "fm_view_ws_path":
        folder = state["repo_folder"]
        ok, result = git.read_file_in_repo(folder, text.strip())
        await db.clear_state(uid)
        if ok:
            await msg.reply(f"👁 **`{folder}/{text.strip()}`**\n\n```\n{result}\n```", reply_markup=main_keyboard())
        else:
            await msg.reply(result, reply_markup=main_keyboard())

    # ── FILE MANAGER: VIEW GITHUB ──────────────────────────────────────────────
    elif action == "fm_view_gh_path":
        repo_url = state["repo_url"]
        token    = await db.get_token(uid)
        await db.clear_state(uid)
        status = await msg.reply("⏳ Fetching file from GitHub...")
        ok, result = git.github_get_file(token, repo_url, text.strip())
        await status.edit_text(f"👁 **`{text.strip()}`** (GitHub)\n\n```\n{result}\n```" if ok else result)

    # ── FILE MANAGER: EDIT LINE — step 1: path ────────────────────────────────
    elif action == "fm_edit_path":
        path = text.strip().lstrip("/\\")
        folder = state["repo_folder"]
        target = os.path.join(config.WORK_DIR, folder, path)
        if not os.path.exists(target):
            await msg.reply(f"❌ `{path}` not found in `{folder}`.")
            return
        try:
            lines   = open(target, "r", errors="ignore").readlines()
            preview = "".join(f"{i+1}: {l.rstrip()}\n" for i, l in enumerate(lines[:30]))
            if len(lines) > 30:
                preview += f"... ({len(lines)} lines total)"
        except Exception:
            preview = "_(could not read file)_"
        await db.set_state(uid, {**state, "action": "fm_edit_linenum", "file_path": path})
        await msg.reply(f"✏️ **`{folder}/{path}`**\n\n```\n{preview[:2000]}\n```\n\nSend the **line number** to edit:")

    # ── FILE MANAGER: EDIT LINE — step 2: line number ─────────────────────────
    elif action == "fm_edit_linenum":
        try:
            line_num = int(text.strip())
        except ValueError:
            await msg.reply("❌ Send a valid line number (e.g. `5`):")
            return
        await db.set_state(uid, {**state, "action": "fm_edit_content", "line_num": line_num})
        await msg.reply(f"✏️ Line **{line_num}**\n\nSend the **new content** for this line:")

    # ── FILE MANAGER: EDIT LINE — step 3: new content ─────────────────────────
    elif action == "fm_edit_content":
        folder   = state["repo_folder"]
        file_path = state["file_path"]
        line_num  = state["line_num"]
        await db.clear_state(uid)
        ok, result = git.edit_file_lines(folder, file_path, line_num, text)
        await msg.reply(result + "\n\n💡 Use **🚀 Git Push** to sync to GitHub.", reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "file_edit", f"{folder}/{file_path}:{line_num}")

    # ── FILE MANAGER: DELETE paths ────────────────────────────────────────────
    elif action == "fm_delete_path":
        folder = state["repo_folder"]
        paths  = [p.strip() for p in text.strip().splitlines() if p.strip()]
        if not paths:
            await msg.reply("❌ No path given. Send file/folder path:")
            return
        await db.clear_state(uid)
        results = []
        for p in paths:
            ok, res = git.delete_path_in_repo(folder, p)
            results.append(res)
        await msg.reply("🗑 **Delete Results:**\n\n" + "\n".join(results) + "\n\n💡 Use **🚀 Git Push** to sync.", reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "file_delete", f"{folder}: {', '.join(paths)}")

    # ── FILE MANAGER: ADD FILE — step 1: path ─────────────────────────────────
    elif action == "fm_add_path":
        path = text.strip().lstrip("/\\")
        await db.set_state(uid, {**state, "action": "fm_add_content", "file_path": path})
        await msg.reply(f"📝 File: `{state['repo_folder']}/{path}`\n\nNow send the **file content:**")

    # ── FILE MANAGER: ADD FILE — step 2: content ──────────────────────────────
    elif action == "fm_add_content":
        folder    = state["repo_folder"]
        file_path = state["file_path"]
        await db.clear_state(uid)
        ok, result = git.write_file_in_repo(folder, file_path, text)
        await msg.reply(result + "\n\n💡 Use **🚀 Git Push** to sync.", reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "file_add", f"{folder}/{file_path}")

    # ── FILE MANAGER: MULTI ADD ────────────────────────────────────────────────
    elif action == "fm_multi_collecting":
        folder       = state["repo_folder"]
        files        = state.get("files", {})
        current_path = state.get("current_path")
        raw          = text.strip()

        if raw.upper() == "DONE":
            await db.clear_state(uid)
            if not files:
                await msg.reply("ℹ️ No files were added.", reply_markup=main_keyboard())
                return
            results = []
            for fpath, fcontent in files.items():
                ok, res = git.write_file_in_repo(folder, fpath, fcontent)
                results.append(res)
            await msg.reply(
                f"📚 **Multi-File Add Complete!**\n\n" + "\n".join(results) +
                f"\n\nTotal: **{len(files)} file(s)**\n\n💡 Use **🚀 Git Push** to sync.",
                reply_markup=main_keyboard()
            )
            await log_action(client, msg.from_user, "multi_file_add", f"{folder}: {len(files)} files")
            return
        if current_path is None:
            path = raw.lstrip("/\\")
            if not path:
                await msg.reply("❌ Send a valid file path:")
                return
            await db.set_state(uid, {**state, "current_path": path})
            await msg.reply(f"📄 Path: `{folder}/{path}`\n\nNow send the **content** for this file:")
        else:
            files[current_path] = raw
            count = len(files)
            await db.set_state(uid, {**state, "files": files, "current_path": None})
            await msg.reply(f"✅ **File {count} saved:** `{current_path}`\n\nFiles queued: {count}\nSend **next file path** or `DONE`:")

    # ── BULK RENAME ────────────────────────────────────────────────────────────
    elif action == "fm_bulk_rename_input":
        folder = state["repo_folder"]
        parts  = [p.strip() for p in text.strip().split("|")]
        if len(parts) < 2:
            await msg.reply("❌ Format: `pattern | prefix | suffix`\nExample: `*.py | new_ |`")
            return
        pattern = parts[0]
        prefix  = parts[1] if len(parts) > 1 else ""
        suffix  = parts[2] if len(parts) > 2 else ""
        await db.clear_state(uid)
        result = git.bulk_rename(folder, pattern, prefix=prefix, suffix=suffix)
        await msg.reply(result + "\n\n💡 Use **🚀 Git Push** to sync.", reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "bulk_rename", f"{folder}: {pattern}")


    # ── RENAME DIR ────────────────────────────────────────────────────────────
    elif action == "rename_dir_new":
        old_name = state["old_name"]
        new_name = text.strip()
        if not new_name:
            await msg.reply("❌ Name can't be empty.")
            return
        await db.clear_state(uid)
        result = git.rename_folder(old_name, new_name)
        await msg.reply(result, reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "rename_dir", f"{old_name} → {new_name}")

    # ── RENAME PATH IN REPO ────────────────────────────────────────────────────
    elif action == "rename_path_old":
        old_path = text.strip().lstrip("/\\")
        if not old_path:
            await msg.reply("❌ Path can't be empty.")
            return
        await db.set_state(uid, {**state, "action": "rename_path_new", "old_path": old_path})
        await msg.reply(f"✂️ Old path: `{old_path}`\n\nSend the **new path:**\nExample: `Demo/Jass/sukh.py`")

    elif action == "rename_path_new":
        old_path    = state["old_path"]
        new_path    = text.strip().lstrip("/\\")
        repo_folder = state["repo_folder"]
        if not new_path:
            await msg.reply("❌ Path can't be empty.")
            return
        await db.clear_state(uid)
        result = git.rename_path_in_repo(repo_folder, old_path, new_path)
        await msg.reply(result + "\n\n💡 Use **🚀 Git Push** to sync to GitHub.", reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "rename_path", f"{repo_folder}: {old_path} → {new_path}")

    # ══════════════════════════════════════════════════════════════════════════
    #  BRANCH OPERATIONS
    # ══════════════════════════════════════════════════════════════════════════
    elif action == "confirm_branch_delete":
        if text.strip().upper() != "DELETE":
            await msg.reply("❌ Type exactly `DELETE` to confirm.",
                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]]))
            return
        branch   = state["branch"]
        repo_url = state["repo_url"]
        token    = await db.get_token(uid)
        await db.clear_state(uid)
        ok, result = git.github_delete_branch(token, repo_url, branch)
        await msg.reply(result, reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "branch_delete", f"{repo_url}: {branch}")

    elif action == "branch_create_name":
        parts    = text.strip().split()
        new_br   = parts[0] if parts else ""
        from_br  = parts[1] if len(parts) > 1 else "main"
        repo_url = state["repo_url"]
        token    = await db.get_token(uid)
        await db.clear_state(uid)
        if not new_br:
            await msg.reply("❌ Invalid format. Send: `new_branch from_branch`")
            return
        ok, result = git.github_create_branch(token, repo_url, new_br, from_branch=from_br)
        await msg.reply(result, reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "branch_create", f"{repo_url}: {new_br} from {from_br}")

    elif action == "branch_merge_input":
        parts    = text.strip().split()
        head     = parts[0] if parts else ""
        base     = parts[1] if len(parts) > 1 else "main"
        repo_url = state["repo_url"]
        token    = await db.get_token(uid)
        await db.clear_state(uid)
        if not head:
            await msg.reply("❌ Invalid format. Send: `head_branch base_branch`")
            return
        status = await msg.reply(f"⏳ Merging `{head}` → `{base}`...")
        ok, result = git.github_merge_branch(token, repo_url, base, head)
        await status.edit_text(result)
        await log_action(client, msg.from_user, "branch_merge", f"{repo_url}: {head} → {base}")

    # ══════════════════════════════════════════════════════════════════════════
    #  COLLABORATOR OPERATIONS
    # ══════════════════════════════════════════════════════════════════════════
    elif action == "collab_add_user":
        parts      = text.strip().split()
        username   = parts[0] if parts else ""
        permission = parts[1] if len(parts) > 1 else "push"
        repo_url   = state["repo_url"]
        token      = await db.get_token(uid)
        await db.clear_state(uid)
        if not username:
            await msg.reply("❌ Send: `username permission`")
            return
        ok, result = git.github_add_collaborator(token, repo_url, username, permission)
        await msg.reply(result, reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "collab_add", f"{repo_url}: {username}")

    elif action == "collab_remove_user":
        username = text.strip()
        repo_url = state["repo_url"]
        token    = await db.get_token(uid)
        await db.clear_state(uid)
        ok, result = git.github_remove_collaborator(token, repo_url, username)
        await msg.reply(result, reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "collab_remove", f"{repo_url}: {username}")

    # ══════════════════════════════════════════════════════════════════════════
    #  GIST OPERATIONS
    # ══════════════════════════════════════════════════════════════════════════
    elif action == "gist_create_filename":
        filename = text.strip()
        if not filename:
            await msg.reply("❌ Filename can't be empty.")
            return
        await db.set_state(uid, {**state, "action": "gist_create_content", "gist_filename": filename})
        await msg.reply(f"📎 Filename: `{filename}`\n\n**Step 2:** Send the **gist content:**")

    elif action == "gist_create_content":
        filename = state["gist_filename"]
        await db.set_state(uid, {**state, "action": "gist_create_vis", "gist_content": text})
        await msg.reply(
            f"📎 Content saved.\n\n**Step 3:** Public or Secret?\n"
            "Reply `yes` = 🔓 Public  or  `no` = 🔒 Secret"
        )

    elif action == "gist_create_vis":
        filename = state["gist_filename"]
        content  = state["gist_content"]
        public   = text.strip().lower() in ("yes", "y", "public", "1")
        token    = await db.get_token(uid)
        await db.clear_state(uid)
        ok, result = git.github_create_gist(token, filename, content, public=public)
        await msg.reply(result, reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "gist_create", filename)

    elif action == "confirm_gist_delete":
        if text.strip().upper() != "DELETE":
            await msg.reply("❌ Type exactly `DELETE` to confirm.",
                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]]))
            return
        gist_id = state["gist_id"]
        token   = await db.get_token(uid)
        await db.clear_state(uid)
        ok, result = git.github_delete_gist(token, gist_id)
        await msg.reply(result, reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "gist_delete", gist_id[:12])

    # ══════════════════════════════════════════════════════════════════════════
    #  PROFILE UPDATE
    # ══════════════════════════════════════════════════════════════════════════
    elif action == "profile_update":
        field  = state["field"]
        value  = None if text.strip() == "-" else text.strip()
        token  = await db.get_token(uid)
        await db.clear_state(uid)
        kwargs = {field: value}
        ok, result = git.github_update_profile(token, **kwargs)
        await msg.reply(result, reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "profile_update", field)

    # ══════════════════════════════════════════════════════════════════════════
    #  GITHUB DELETE FLOWS
    # ══════════════════════════════════════════════════════════════════════════
    elif action == "confirm_gh_delete_name":
        if text.strip().upper() != "DELETE":
            await msg.reply("❌ Type exactly `DELETE` to confirm.",
                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]]))
            return
        repo_url  = state["url"]
        repo_name = state.get("name", repo_url)
        token     = await db.get_token(uid)
        await db.clear_state(uid)
        status = await msg.reply(f"⏳ Deleting `{repo_name}` from GitHub...")
        ok, result = git.github_delete_repo(token, repo_url)
        await status.edit_text(result)
        if ok:
            repos = await db.get_repos(uid)
            await db.set_repos(uid, [r for r in repos if r["url"] != repo_url])
            await msg.reply("🗑 Also removed from your saved list.", reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "repo_delete_gh", repo_name)

    elif action == "confirm_gh_delete":
        if text.strip().upper() != "DELETE":
            await msg.reply("❌ Type exactly `DELETE` to confirm.",
                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]]))
            return
        repo_url = state["url"]
        name     = state.get("name", repo_url)
        token    = await db.get_token(uid)
        await db.clear_state(uid)
        status   = await msg.reply(f"⏳ Deleting `{name}`...")
        ok, result = git.github_delete_repo(token, repo_url)
        await status.edit_text(result)
        if ok:
            repos = await db.get_repos(uid)
            await db.set_repos(uid, [r for r in repos if r["url"] != repo_url])
            await msg.reply("🗑 Removed from saved list.", reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "repo_delete_gh", name)

    # ══════════════════════════════════════════════════════════════════════════
    #  CREATE REPO FLOW
    # ══════════════════════════════════════════════════════════════════════════
    elif action == "create_repo_name":
        repo_name = text.strip().replace(" ", "-")
        if not repo_name:
            await msg.reply("❌ Name can't be empty.")
            return
        await db.set_state(uid, {"action": "create_repo_priv", "name": repo_name})
        await msg.reply(f"🆕 Repo name: **{repo_name}**\n\n**Step 2:** Private or Public?\n`yes` = 🔒 Private  `no` = 🔓 Public")

    elif action == "create_repo_priv":
        private = text.strip().lower() in ("yes", "y", "1", "private")
        lock    = "🔒 Private" if private else "🔓 Public"
        await db.set_state(uid, {**state, "action": "create_repo_desc", "private": private})
        await msg.reply(f"🆕 **{state['name']}** — {lock}\n\n**Step 3:** Send a **description** (or `-` to skip):")

    elif action == "create_repo_desc":
        desc    = "" if text.strip() == "-" else text.strip()
        token   = await db.get_token(uid)
        name    = state["name"]
        private = state.get("private", False)
        await db.clear_state(uid)
        status = await msg.reply(f"⏳ Creating `{name}` on GitHub...")
        ok, result, url = git.github_create_repo(token, name, private=private, description=desc)
        await status.edit_text(result)
        if ok and url:
            added = await db.add_repo(uid, url, name, private)
            await db.set_active_repo(uid, url)
            await msg.reply("📌 Auto-saved & set as active repo!", reply_markup=main_keyboard())
        await log_action(client, msg.from_user, "repo_create", name)

    # ══════════════════════════════════════════════════════════════════════════
    #  CLEAN DATA
    # ══════════════════════════════════════════════════════════════════════════
    elif action == "confirm_clean":
        if text.strip().upper() != "CLEAN":
            await msg.reply("❌ Type exactly `CLEAN` to confirm.",
                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="go_home")]]))
            return
        await db.clean_user_data(uid)
        await msg.reply(
            "🧹 **All your data cleaned!**\n\n✅ Token deleted\n✅ Repos deleted\n✅ States cleared\n\nStart fresh with /start",
            reply_markup=main_keyboard()
        )
        await alert_owner(client, f"🧹 **User cleaned data**\n👤 {utag(msg.from_user)}\n🕐 {ts()}")

    # ══════════════════════════════════════════════════════════════════════════
    #  OWNER: BROADCAST
    # ══════════════════════════════════════════════════════════════════════════
    elif action == "owner_broadcast" and uid == config.OWNER_ID:
        users = await db.get_all_users()
        await db.clear_state(uid)
        status   = await msg.reply(f"📢 Broadcasting to {len(users)} users...")
        sent     = 0
        failed   = 0
        for u in users:
            try:
                await app.send_message(u["_id"], text)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        await status.edit_text(f"📢 **Broadcast done!**\n✅ Sent: {sent}\n❌ Failed: {failed}", reply_markup=main_keyboard())

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    else:
        await msg.reply("👋 Use the buttons below or /start", reply_markup=main_keyboard())


# ══════════════════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{'='*52}")
    print(f"  🤖 GitHub Control Bot v5.0")
    print(f"  📦 Workspace : {config.WORK_DIR}")
    print(f"  🗄  MongoDB   : {config.MONGO_URI[:35]}...")
    print(f"  👑 Owner     : {config.OWNER_ID}")
    print(f"{'='*52}\n")
    app.run()
