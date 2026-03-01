"""
git_utils.py — File system & Git operations for GitHub Control Bot
"""

import os
import re
import shutil
import zipfile
import subprocess
import requests
from pathlib import Path
from config import WORK_DIR


def repo_short(url: str) -> str:
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else url


# ══════════════════════════════════════════════════════════════════════════════
#  FILE OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def list_workspace() -> str:
    items = sorted(
        i for i in os.listdir(WORK_DIR)
        if not i.endswith(".zip") and os.path.isdir(os.path.join(WORK_DIR, i))
    )
    if not items:
        return "📂 Workspace is empty."
    lines = "\n".join(f"  • `{x}`" for x in items)
    return f"📂 **Workspace folders:**\n{lines}"


def grep_text(directory: str, search: str, only_py: bool = False) -> str:
    results = []
    pattern = re.compile(re.escape(search))
    for root, _, files in os.walk(directory):
        for fname in files:
            if only_py and not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if pattern.search(line):
                            rel = os.path.relpath(fpath, directory)
                            results.append(f"`{rel}:{lineno}` — {line.strip()}")
            except Exception:
                pass
    return "\n".join(results) if results else "❌ No matches found."


def replace_text(directory: str, old: str, new: str, only_py: bool = True) -> str:
    changed = []
    for root, _, files in os.walk(directory):
        for fname in files:
            if only_py and not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    content = f.read()
                if old in content:
                    with open(fpath, "w") as f:
                        f.write(content.replace(old, new))
                    changed.append(os.path.relpath(fpath, directory))
            except Exception:
                pass
    if changed:
        return "✅ Replaced in:\n" + "\n".join(f"• `{x}`" for x in changed)
    return "❌ No files changed."


def make_zip(src_dir: str, zip_path: str) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for file in files:
                fp = os.path.join(root, file)
                zf.write(fp, os.path.relpath(fp, src_dir))


def rename_folder(old_name: str, new_name: str) -> str:
    old_path = os.path.join(WORK_DIR, old_name)
    new_path = os.path.join(WORK_DIR, new_name)
    if not os.path.exists(old_path):
        return f"❌ Folder `{old_name}` not found."
    if os.path.exists(new_path):
        return f"❌ `{new_name}` already exists."
    os.rename(old_path, new_path)
    return f"✅ Renamed `{old_name}` → `{new_name}`"


# ══════════════════════════════════════════════════════════════════════════════
#  CLONE  — handles both public and private repos
# ══════════════════════════════════════════════════════════════════════════════

def clone_repo(repo_url: str, dest: str, token: str | None = None) -> tuple[bool, str]:
    """
    Clone a GitHub repo.
    - If token provided → authenticated clone (works for private repos)
    - If no token → unauthenticated clone (public repos only)
    
    Returns: (success: bool, message: str)
    """
    try:
        if os.path.exists(dest):
            shutil.rmtree(dest)

        # Build clone URL
        if token:
            # Inject token into URL: https://TOKEN@github.com/user/repo.git
            m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
            if not m:
                return False, "❌ Invalid GitHub URL."
            repo_path = m.group(1)
            clone_url = f"https://{token}@github.com/{repo_path}.git"
        else:
            # Public clone — ensure it's https format
            clone_url = repo_url
            if clone_url.startswith("git@"):
                # Convert SSH to HTTPS
                clone_url = re.sub(r"git@github\.com:(.+?)(?:\.git)?$",
                                   r"https://github.com/\1.git", clone_url)

        result = subprocess.run(
            ["git", "clone", "--depth=1", clone_url, dest],
            capture_output=True, text=True, timeout=120
        )

        if result.returncode == 0:
            folder = os.path.basename(dest)
            return True, f"✅ Cloned `{folder}` successfully!"
        
        stderr = result.stderr.strip()
        
        # Detect if private repo needs token
        if any(x in stderr.lower() for x in [
            "authentication failed", "repository not found",
            "could not read username", "403", "401"
        ]):
            return False, "NEEDS_TOKEN"
        
        return False, f"❌ Clone failed:\n`{stderr}`"

    except subprocess.TimeoutExpired:
        return False, "❌ Clone timed out (>120s). Check your network."
    except Exception as e:
        return False, f"❌ Error: {e}"


# ══════════════════════════════════════════════════════════════════════════════
#  GIT PUSH
# ══════════════════════════════════════════════════════════════════════════════

def git_push(directory: str, token: str, repo_url: str, branch: str = "main") -> str:
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m:
            return "❌ Invalid GitHub repo URL."
        repo_path = m.group(1)
        auth_url  = f"https://{token}@github.com/{repo_path}.git"

        original_dir = os.getcwd()
        os.chdir(directory)

        cmds = [
            ["git", "init"],
            ["git", "add", "."],
            ["git", "commit", "-m", f"Bot push — {Path(directory).name}"],
            ["git", "remote", "remove", "origin"],
            ["git", "remote", "add", "origin", auth_url],
            ["git", "push", "-u", "origin", branch, "--force"],
        ]
        errs = []
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0 and "already exists" not in r.stderr:
                errs.append(r.stderr.strip())

        os.chdir(original_dir)
        return "✅ Pushed to GitHub!" if not errs else "⚠️ " + "\n".join(errs)

    except Exception as e:
        try:
            os.chdir(WORK_DIR)
        except Exception:
            pass
        return f"❌ Git error: {e}"


# ══════════════════════════════════════════════════════════════════════════════
#  GITHUB RELEASE UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def upload_to_github(zip_path: str, token: str, repo_url: str) -> str:
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m:
            return "❌ Invalid GitHub repo URL."
        repo_name = m.group(1)
        zip_name  = os.path.basename(zip_path)

        with open(zip_path, "rb") as f:
            data = f.read()

        headers = {
            "Authorization": f"token {token}",
            "Accept":        "application/vnd.github+json",
        }

        # Try to get latest release
        r = requests.get(
            f"https://api.github.com/repos/{repo_name}/releases/latest",
            headers=headers, timeout=30
        )
        if r.status_code == 200:
            upload_url = r.json()["upload_url"].replace("{?name,label}", f"?name={zip_name}")
        else:
            # Create a new release
            cr = requests.post(
                f"https://api.github.com/repos/{repo_name}/releases",
                headers=headers,
                json={"tag_name": "bot-release", "name": "Bot Upload", "body": "Auto-uploaded by bot"},
                timeout=30,
            )
            if cr.status_code not in (200, 201):
                return f"❌ Could not create release:\n`{cr.text}`"
            upload_url = cr.json()["upload_url"].replace("{?name,label}", f"?name={zip_name}")

        up = requests.post(
            upload_url,
            headers={**headers, "Content-Type": "application/zip"},
            data=data, timeout=120
        )
        if up.status_code in (200, 201):
            dl_url = up.json().get("browser_download_url", "")
            return f"✅ Uploaded to GitHub!\n🔗 {dl_url}"
        return f"❌ Upload failed:\n`{up.text}`"

    except Exception as e:
        return f"❌ Error: {e}"
