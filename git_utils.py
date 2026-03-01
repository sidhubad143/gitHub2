"""git_utils.py — All file system, git, zip operations"""
import os, re, shutil, zipfile, subprocess, requests
from pathlib import Path
from config import WORK_DIR


def repo_short(url: str) -> str:
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else url


def get_workspace_folders() -> list[str]:
    """Return sorted list of folder names in workspace (no .zip files)."""
    try:
        return sorted(
            i for i in os.listdir(WORK_DIR)
            if os.path.isdir(os.path.join(WORK_DIR, i)) and not i.startswith(".")
        )
    except Exception:
        return []


def list_workspace() -> str:
    items = get_workspace_folders()
    if not items:
        return "📂 Workspace is empty — clone a repo first!"
    return "📂 **Workspace folders:**\n" + "\n".join(f"  • `{x}`" for x in items)


def grep_text(directory: str, search: str, only_py: bool = False) -> str:
    results = []
    pattern = re.compile(re.escape(search), re.IGNORECASE)
    for root, _, files in os.walk(directory):
        for fname in sorted(files):
            if only_py and not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if pattern.search(line):
                            rel = os.path.relpath(fpath, directory)
                            results.append(f"`{rel}:{lineno}` {line.strip()[:80]}")
            except Exception:
                pass
    if not results:
        return "❌ No matches found."
    return "\n".join(results)


def replace_text(directory: str, old: str, new: str, only_py: bool = True) -> str:
    changed = []
    for root, _, files in os.walk(directory):
        for fname in files:
            if only_py and not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            try:
                content = open(fpath, "r", errors="ignore").read()
                if old in content:
                    open(fpath, "w").write(content.replace(old, new))
                    changed.append(os.path.relpath(fpath, directory))
            except Exception:
                pass
    if changed:
        return "✅ Replaced in:\n" + "\n".join(f"• `{x}`" for x in changed)
    return "❌ No occurrences found — nothing changed."


def make_zip(src_dir: str, zip_path: str) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for file in files:
                fp = os.path.join(root, file)
                zf.write(fp, os.path.relpath(fp, src_dir))


def rename_folder(old_name: str, new_name: str) -> str:
    # Strip any accidental whitespace
    old_name = old_name.strip()
    new_name = new_name.strip()
    # Reject invalid chars in folder name
    bad = set('/\\:*?"<>|')
    if any(c in bad for c in new_name):
        return f"❌ Invalid name — don't use: / \\ : * ? \" < > |"
    old = os.path.join(WORK_DIR, old_name)
    new = os.path.join(WORK_DIR, new_name)
    if not os.path.exists(old):
        return (
            f"❌ Folder `{old_name}` not found in workspace.\n\n"
            f"{list_workspace()}"
        )
    if os.path.exists(new):
        return f"❌ A folder named `{new_name}` already exists."
    try:
        os.rename(old, new)
    except Exception as e:
        return f"❌ Rename failed: {e}"
    # Also rename any zip that matched old name
    old_zip = os.path.join(WORK_DIR, f"{old_name}.zip")
    new_zip = os.path.join(WORK_DIR, f"{new_name}.zip")
    if os.path.exists(old_zip) and not os.path.exists(new_zip):
        try:
            os.rename(old_zip, new_zip)
        except Exception:
            pass
    return f"✅ Renamed `{old_name}` → `{new_name}`"


def clone_repo(repo_url: str, dest: str, token: str | None = None) -> tuple[bool, str]:
    """Returns (success, message). message can be 'NEEDS_TOKEN' special value."""
    try:
        if os.path.exists(dest):
            shutil.rmtree(dest)

        if token:
            m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
            if not m:
                return False, "❌ Invalid GitHub URL."
            clone_url = f"https://{token}@github.com/{m.group(1)}.git"
        else:
            clone_url = repo_url
            if clone_url.startswith("git@"):
                clone_url = re.sub(
                    r"git@github\.com:(.+?)(?:\.git)?$",
                    r"https://github.com/\1.git", clone_url
                )

        r = subprocess.run(
            ["git", "clone", "--depth=1", clone_url, dest],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            return True, f"✅ Cloned `{Path(dest).name}` successfully!"

        err = r.stderr.lower()
        if any(x in err for x in ["authentication", "not found", "could not read", "403", "401", "repository"]):
            return False, "NEEDS_TOKEN"

        return False, f"❌ Clone failed:\n`{r.stderr.strip()[:500]}`"

    except subprocess.TimeoutExpired:
        return False, "❌ Clone timed out (>120s)."
    except Exception as e:
        return False, f"❌ Error: {e}"


def git_push(directory: str, token: str, repo_url: str, branch: str = "main") -> str:
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m:
            return "❌ Invalid GitHub repo URL."
        auth_url = f"https://{token}@github.com/{m.group(1)}.git"
        orig = os.getcwd()
        os.chdir(directory)
        errs = []
        for cmd in [
            ["git", "init"],
            ["git", "add", "."],
            ["git", "commit", "-m", f"Bot push — {Path(directory).name}"],
            ["git", "remote", "remove", "origin"],
            ["git", "remote", "add", "origin", auth_url],
            ["git", "push", "-u", "origin", branch, "--force"],
        ]:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0 and "already exists" not in r.stderr:
                errs.append(r.stderr.strip())
        os.chdir(orig)
        return "✅ Pushed to GitHub!" if not errs else "⚠️ " + "\n".join(e for e in errs if e)
    except Exception as e:
        try: os.chdir(WORK_DIR)
        except: pass
        return f"❌ Git error: {e}"


def unzip_and_push(zip_path: str, token: str, repo_url: str, branch: str = "main") -> tuple[bool, str]:
    """
    Extract ZIP to a temp folder, then git push all files to GitHub repo.
    Returns (success, message).
    Steps:
      1. Extract zip → temp dir
      2. git init, add all, commit, push --force to repo
      3. Clean up temp dir
    """
    import tempfile
    temp_dir = None
    try:
        # Extract ZIP
        temp_dir = tempfile.mkdtemp(dir=WORK_DIR, prefix="_upload_tmp_")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)

        # Check if ZIP had a single root folder (common case)
        # e.g. zip contains myrepo/file1.py, myrepo/file2.py
        # → push from myrepo/ not from the temp dir
        contents = os.listdir(temp_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(temp_dir, contents[0])):
            push_dir = os.path.join(temp_dir, contents[0])
        else:
            push_dir = temp_dir

        result = git_push(push_dir, token, repo_url, branch)
        return True, result

    except zipfile.BadZipFile:
        return False, "❌ Invalid ZIP file — could not extract."
    except Exception as e:
        return False, f"❌ Extract error: {e}"
    finally:
        # Always clean up temp dir
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


def upload_zip_as_release(zip_path: str, token: str, repo_url: str) -> str:
    """Upload a ZIP file as a GitHub Release asset (binary attachment)."""
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m:
            return "❌ Invalid GitHub repo URL."
        repo_name = m.group(1)
        zip_name  = os.path.basename(zip_path)
        data      = open(zip_path, "rb").read()
        headers   = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

        # Try latest release, else create one
        r = requests.get(f"https://api.github.com/repos/{repo_name}/releases/latest",
                         headers=headers, timeout=30)
        if r.status_code == 200:
            upload_url = r.json()["upload_url"].replace("{?name,label}", f"?name={zip_name}")
        else:
            cr = requests.post(
                f"https://api.github.com/repos/{repo_name}/releases",
                headers=headers,
                json={"tag_name": "bot-release", "name": "Bot Upload", "body": "Auto-uploaded"},
                timeout=30,
            )
            if cr.status_code not in (200, 201):
                return f"❌ Could not create release:\n`{cr.text[:300]}`"
            upload_url = cr.json()["upload_url"].replace("{?name,label}", f"?name={zip_name}")

        up = requests.post(
            upload_url,
            headers={**headers, "Content-Type": "application/zip"},
            data=data, timeout=120
        )
        if up.status_code in (200, 201):
            dl = up.json().get("browser_download_url", "")
            return f"✅ Uploaded to GitHub Releases!\n🔗 {dl}"
        return f"❌ Upload failed:\n`{up.text[:300]}`"
    except Exception as e:
        return f"❌ Error: {e}"
