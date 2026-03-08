"""git_utils.py — All filesystem, git, GitHub API operations v5.0"""
import os, re, shutil, zipfile, subprocess, requests
from pathlib import Path
from config import WORK_DIR

def _H(token): return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

# ══ WORKSPACE ══════════════════════════════════════════════════════════════════
def repo_short(url):
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else url

def get_workspace_folders():
    """Returns list of valid git workspace folders, excluding temp/hidden."""
    try:
        os.makedirs(WORK_DIR, exist_ok=True)
        return sorted(
            i for i in os.listdir(WORK_DIR)
            if os.path.isdir(os.path.join(WORK_DIR, i))
            and not i.startswith(".")
            and not i.startswith("_")   # exclude temp folders like _upload_tmp_
        )
    except Exception:
        return []

def list_workspace():
    items = get_workspace_folders()
    if not items: return "📂 Workspace is empty — clone a repo first!"
    return "📂 **Workspace folders:**\n" + "\n".join(f"  • `{x}`" for x in items)

def list_tree(directory, max_lines=50):
    lines = []
    try:
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in sorted(dirs) if d != ".git"]
            lvl = root.replace(directory, "").count(os.sep)
            ind = "  " * lvl
            fn  = os.path.basename(root)
            lines.append(f"{'📁' if lvl else '📁'} `{fn}/`" if not lvl else f"{ind}📁 `{fn}/`")
            for f in sorted(files):
                lines.append(f"{'  '*(lvl+1)}• `{f}`")
            if len(lines) > max_lines:
                lines.append("  _...more files..._"); break
    except: return "_(could not read folder)_"
    return "\n".join(lines) if lines else "_(empty)_"

def make_zip(src_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for file in files:
                fp = os.path.join(root, file)
                zf.write(fp, os.path.relpath(fp, src_dir))

# ══ FILE OPS ═══════════════════════════════════════════════════════════════════
def grep_text(directory, search, only_py=False):
    results = []
    pattern = re.compile(re.escape(search), re.IGNORECASE)
    for root, _, files in os.walk(directory):
        for fname in sorted(files):
            if only_py and not fname.endswith(".py"): continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if pattern.search(line):
                            rel = os.path.relpath(fpath, directory)
                            results.append(f"`{rel}:{lineno}` {line.strip()[:80]}")
            except: pass
    return "\n".join(results) if results else "❌ No matches found."

def replace_text(directory, old, new, only_py=True):
    changed = []
    for root, _, files in os.walk(directory):
        for fname in files:
            if only_py and not fname.endswith(".py"): continue
            fpath = os.path.join(root, fname)
            try:
                c = open(fpath, "r", errors="ignore").read()
                if old in c:
                    open(fpath, "w").write(c.replace(old, new))
                    changed.append(os.path.relpath(fpath, directory))
            except: pass
    return ("✅ Replaced in:\n" + "\n".join(f"• `{x}`" for x in changed)) if changed else "❌ No occurrences found."

def rename_folder(old_name, new_name):
    old_name, new_name = old_name.strip(), new_name.strip()
    if any(c in set('/\\:*?"<>|') for c in new_name):
        return "❌ Invalid name — don't use: / \\ : * ? \" < > |"
    old, new = os.path.join(WORK_DIR, old_name), os.path.join(WORK_DIR, new_name)
    if not os.path.exists(old): return f"❌ Folder `{old_name}` not found.\n\n{list_workspace()}"
    if os.path.exists(new): return f"❌ `{new_name}` already exists."
    try: os.rename(old, new)
    except Exception as e: return f"❌ Rename failed: {e}"
    oz, nz = os.path.join(WORK_DIR, f"{old_name}.zip"), os.path.join(WORK_DIR, f"{new_name}.zip")
    if os.path.exists(oz) and not os.path.exists(nz):
        try: os.rename(oz, nz)
        except: pass
    return f"✅ Renamed `{old_name}` → `{new_name}`"

def rename_path_in_repo(repo_folder, old_rel, new_rel):
    repo_folder = repo_folder.strip()
    old_rel = old_rel.strip().lstrip("/\\")
    new_rel = new_rel.strip().lstrip("/\\")
    repo_dir = os.path.join(WORK_DIR, repo_folder)
    if not os.path.exists(repo_dir): return f"❌ Repo folder `{repo_folder}` not found."
    old_path, new_path = os.path.join(repo_dir, old_rel), os.path.join(repo_dir, new_rel)
    if not os.path.exists(old_path): return f"❌ Path `{old_rel}` not found."
    if os.path.exists(new_path): return f"❌ `{new_rel}` already exists."
    old_base, new_base = os.path.basename(old_rel), os.path.basename(new_rel)
    text_changed = []
    if old_base != new_base:
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d != ".git"]
            for fname in files:
                if not fname.endswith(".py"): continue
                fpath = os.path.join(root, fname)
                try:
                    c = open(fpath, "r", errors="ignore").read()
                    if old_base in c:
                        open(fpath, "w").write(c.replace(old_base, new_base))
                        text_changed.append(os.path.relpath(fpath, repo_dir))
                except: pass
    os.makedirs(os.path.dirname(new_path) or repo_dir, exist_ok=True)
    try: os.rename(old_path, new_path)
    except Exception as e: return f"❌ Rename failed: {e}"
    msg = f"✅ Renamed `{repo_folder}/{old_rel}` → `{repo_folder}/{new_rel}`"
    if text_changed:
        msg += f"\n📝 Also replaced in {len(text_changed)} file(s):\n" + "\n".join(f"• `{f}`" for f in text_changed[:10])
    return msg

def delete_path_in_repo(repo_folder, rel_path):
    repo_folder = repo_folder.strip()
    rel_path = rel_path.strip().lstrip("/\\")
    target = os.path.join(WORK_DIR, repo_folder, rel_path)
    if not os.path.exists(os.path.join(WORK_DIR, repo_folder)):
        return False, f"❌ Folder `{repo_folder}` not found."
    if not os.path.exists(target):
        return False, f"❌ `{rel_path}` not found inside `{repo_folder}`."
    try:
        if os.path.isdir(target): shutil.rmtree(target); return True, f"✅ Deleted folder `{repo_folder}/{rel_path}`"
        else: os.remove(target); return True, f"✅ Deleted file `{repo_folder}/{rel_path}`"
    except Exception as e: return False, f"❌ Delete failed: {e}"

def write_file_in_repo(repo_folder, rel_path, content):
    repo_folder = repo_folder.strip()
    rel_path = rel_path.strip().lstrip("/\\")
    repo_dir = os.path.join(WORK_DIR, repo_folder)
    if not os.path.exists(repo_dir): return False, f"❌ Folder `{repo_folder}` not found."
    target = os.path.join(repo_dir, rel_path)
    parent = os.path.dirname(target)
    if parent: os.makedirs(parent, exist_ok=True)
    existed = os.path.exists(target)
    try:
        open(target, "w", encoding="utf-8").write(content)
        return True, f"✅ {'Updated' if existed else 'Created'} `{repo_folder}/{rel_path}`"
    except Exception as e: return False, f"❌ Write failed: {e}"

def read_file_in_repo(repo_folder, rel_path):
    target = os.path.join(WORK_DIR, repo_folder.strip(), rel_path.strip().lstrip("/\\"))
    if not os.path.exists(target): return False, f"❌ File not found: `{rel_path}`"
    if os.path.isdir(target): return False, f"❌ `{rel_path}` is a folder, not a file."
    try:
        content = open(target, "r", errors="ignore").read()
        if len(content) > 3500: content = content[:3500] + f"\n\n_...truncated ({len(content)} chars total)_"
        return True, content
    except Exception as e: return False, f"❌ Read failed: {e}"

def edit_file_lines(repo_folder, rel_path, line_num, new_line):
    target = os.path.join(WORK_DIR, repo_folder.strip(), rel_path.strip().lstrip("/\\"))
    if not os.path.exists(target): return False, f"❌ `{rel_path}` not found."
    try:
        lines = open(target, "r", errors="ignore").readlines()
        if not (1 <= line_num <= len(lines)): return False, f"❌ Line {line_num} doesn't exist. File has {len(lines)} lines."
        old = lines[line_num-1].rstrip()
        lines[line_num-1] = new_line + "\n"
        open(target, "w").writelines(lines)
        return True, f"✅ Line {line_num} updated.\n**Old:** `{old[:80]}`\n**New:** `{new_line[:80]}`"
    except Exception as e: return False, f"❌ Edit failed: {e}"

def bulk_rename(repo_folder, pattern, prefix="", suffix="", replace_from="", replace_to=""):
    import fnmatch
    repo_dir = os.path.join(WORK_DIR, repo_folder)
    if not os.path.exists(repo_dir): return f"❌ Folder `{repo_folder}` not found."
    renamed = []
    for root, _, files in os.walk(repo_dir):
        for fname in files:
            if fnmatch.fnmatch(fname, pattern):
                base, ext = os.path.splitext(fname)
                new_base = base.replace(replace_from, replace_to) if replace_from else prefix + base + suffix
                new_fname = new_base + ext
                if new_fname != fname:
                    old_p, new_p = os.path.join(root, fname), os.path.join(root, new_fname)
                    if not os.path.exists(new_p):
                        os.rename(old_p, new_p)
                        renamed.append(f"`{fname}` → `{new_fname}`")
    return (f"✅ Renamed {len(renamed)} file(s):\n" + "\n".join(renamed[:20])) if renamed else f"❌ No files matched `{pattern}`."

# ══ GIT OPS ════════════════════════════════════════════════════════════════════
def _env():
    return {**os.environ, "GIT_AUTHOR_NAME": "GitHub Bot", "GIT_AUTHOR_EMAIL": "bot@github.com",
            "GIT_COMMITTER_NAME": "GitHub Bot", "GIT_COMMITTER_EMAIL": "bot@github.com"}

def clone_repo(repo_url, dest, token=None):
    try:
        if os.path.exists(dest): shutil.rmtree(dest)
        if token:
            m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
            if not m: return False, "❌ Invalid GitHub URL."
            clone_url = f"https://{token}@github.com/{m.group(1)}.git"
        else:
            clone_url = re.sub(r"git@github\.com:(.+?)(?:\.git)?$", r"https://github.com/\1.git", repo_url) if repo_url.startswith("git@") else repo_url
        r = subprocess.run(["git", "clone", "--depth=1", clone_url, dest], capture_output=True, text=True, timeout=120)
        if r.returncode == 0: return True, f"✅ Cloned `{Path(dest).name}` successfully!"
        err = r.stderr.lower()
        if any(x in err for x in ["authentication", "not found", "could not read", "403", "401"]): return False, "NEEDS_TOKEN"
        return False, f"❌ Clone failed:\n`{r.stderr.strip()[:400]}`"
    except subprocess.TimeoutExpired: return False, "❌ Clone timed out."
    except Exception as e: return False, f"❌ Error: {e}"

def git_push(directory, token, repo_url, branch="main"):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return "❌ Invalid GitHub repo URL."
        auth_url = f"https://{token}@github.com/{m.group(1)}.git"
        orig = os.getcwd(); os.chdir(directory)
        env = _env()

        def run(cmd, ignore_errors=False):
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
            return r

        # Step 1: init + config
        run(["git", "init"])
        run(["git", "config", "user.email", "bot@github.com"])
        run(["git", "config", "user.name",  "GitHub Bot"])

        # Step 2: stage all files
        r = run(["git", "add", "."])
        if r.returncode != 0:
            os.chdir(orig); return f"❌ git add failed:\n`{r.stderr.strip()[:200]}`"

        # Step 3: commit
        run(["git", "commit", "--allow-empty", "-m", f"Bot push — {Path(directory).name}"])

        # Step 4: set branch
        run(["git", "branch", "-M", branch])

        # Step 5: set remote — remove first only if it exists, then add
        existing = run(["git", "remote"])
        if "origin" in existing.stdout:
            run(["git", "remote", "set-url", "origin", auth_url])
        else:
            run(["git", "remote", "add", "origin", auth_url])

        # Step 6: push
        r = run(["git", "push", "-u", "origin", branch, "--force"])
        os.chdir(orig)
        if r.returncode == 0:
            return "✅ Pushed to GitHub!"
        err = r.stderr.strip()
        if "authentication" in err.lower() or "403" in err or "401" in err:
            return "❌ Auth failed — check your GitHub token has `repo` scope."
        if "rejected" in err.lower():
            return f"❌ Push rejected by GitHub:\n`{err[:250]}`"
        return f"⚠️ Push issue:\n`{err[:300]}`"
    except Exception as e:
        try: os.chdir(WORK_DIR)
        except: pass
        return f"❌ Git error: {e}"

def git_pull(directory, token=None, repo_url=None):
    try:
        if not os.path.exists(directory): return f"❌ Folder not found."
        if not os.path.exists(os.path.join(directory, ".git")): return "❌ Not a git repo — clone it first."
        orig = os.getcwd(); os.chdir(directory)
        if token and repo_url:
            m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
            if m: subprocess.run(["git", "remote", "set-url", "origin", f"https://{token}@github.com/{m.group(1)}.git"], capture_output=True, text=True, timeout=30)
        r = subprocess.run(["git", "pull", "--rebase"], capture_output=True, text=True, timeout=120)
        os.chdir(orig)
        if r.returncode == 0: return f"✅ **Git Pull done!**\n`{r.stdout.strip() or 'Already up to date.'}`"
        err = r.stderr.strip()
        if "authentication" in err.lower() or "403" in err: return "❌ Auth failed — check your token."
        return f"❌ Pull failed:\n`{err[:300]}`"
    except Exception as e:
        try: os.chdir(WORK_DIR)
        except: pass
        return f"❌ Git error: {e}"

def unzip_and_push(zip_path, token, repo_url, branch="main"):
    import tempfile
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(dir=WORK_DIR, prefix="_upload_tmp_")
        with zipfile.ZipFile(zip_path, "r") as zf: zf.extractall(temp_dir)
        contents = os.listdir(temp_dir)
        push_dir = os.path.join(temp_dir, contents[0]) if len(contents) == 1 and os.path.isdir(os.path.join(temp_dir, contents[0])) else temp_dir
        return True, git_push(push_dir, token, repo_url, branch)
    except zipfile.BadZipFile: return False, "❌ Invalid ZIP file."
    except Exception as e: return False, f"❌ Extract error: {e}"
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try: shutil.rmtree(temp_dir)
            except: pass

# ══ GITHUB API — REPOS ═════════════════════════════════════════════════════════
def github_list_repos(token):
    try:
        all_repos, page = [], 1
        while True:
            r = requests.get(f"https://api.github.com/user/repos?per_page=100&page={page}&sort=updated", headers=_H(token), timeout=30)
            if r.status_code != 200: return False, [], f"❌ GitHub error: {r.json().get('message', r.text[:200])}"
            data = r.json()
            if not data: break
            all_repos.extend(data)
            if len(data) < 100: break
            page += 1
        return True, all_repos, ""
    except Exception as e: return False, [], f"❌ Error: {e}"

def github_create_repo(token, name, private=False, description=""):
    try:
        name = name.strip().replace(" ", "-")
        r = requests.post("https://api.github.com/user/repos", headers=_H(token),
                          json={"name": name, "private": private, "description": description, "auto_init": False}, timeout=30)
        if r.status_code in (200, 201):
            url = r.json().get("html_url", "")
            return True, f"✅ **Repo created!**\n📁 **{name}** — {'🔒 Private' if private else '🔓 Public'}\n🔗 `{url}`", url
        err = r.json().get("message", r.text[:200])
        return False, f"❌ {'Repo already exists.' if 'already exists' in err.lower() else f'GitHub error: `{err}`'}", ""
    except Exception as e: return False, f"❌ Error: {e}", ""

def github_delete_repo(token, repo_url):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        r = requests.delete(f"https://api.github.com/repos/{m.group(1)}", headers=_H(token), timeout=30)
        if r.status_code == 204: return True, f"✅ **Repo deleted!**\n🗑 `{repo_url}`"
        if r.status_code == 403: return False, "❌ Permission denied — token needs `delete_repo` scope."
        if r.status_code == 404: return False, "❌ Repo not found on GitHub."
        return False, f"❌ GitHub error: `{r.json().get('message', r.text[:200])}`"
    except Exception as e: return False, f"❌ Error: {e}"

def github_set_visibility(token, repo_url, private):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        r = requests.patch(f"https://api.github.com/repos/{m.group(1)}", headers=_H(token), json={"private": private}, timeout=30)
        if r.status_code == 200: return True, f"✅ Repo is now **{'🔒 Private' if private else '🔓 Public'}**"
        return False, f"❌ GitHub error: `{r.json().get('message', r.text[:200])}`"
    except Exception as e: return False, f"❌ Error: {e}"

def github_get_commits(token, repo_url, limit=10):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        r = requests.get(f"https://api.github.com/repos/{m.group(1)}/commits?per_page={limit}", headers=_H(token), timeout=30)
        if r.status_code != 200: return False, f"❌ GitHub error: `{r.json().get('message', '')}`"
        commits = r.json()
        if not commits: return True, "📭 No commits found."
        lines = []
        for c in commits:
            sha = c["sha"][:7]; msg = c["commit"]["message"].split("\n")[0][:55]
            author = c["commit"]["author"]["name"][:18]; date = c["commit"]["author"]["date"][:10]
            lines.append(f"`{sha}` **{msg}**\n   👤 {author} • {date}")
        return True, "\n\n".join(lines)
    except Exception as e: return False, f"❌ Error: {e}"

def github_get_file(token, repo_url, path, branch="main"):
    try:
        import base64
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        r = requests.get(f"https://api.github.com/repos/{m.group(1)}/contents/{path}?ref={branch}", headers=_H(token), timeout=30)
        if r.status_code == 404: return False, f"❌ File `{path}` not found in repo."
        if r.status_code != 200: return False, f"❌ GitHub error: `{r.json().get('message', '')}`"
        content = base64.b64decode(r.json()["content"]).decode("utf-8", errors="ignore")
        if len(content) > 3500: content = content[:3500] + f"\n\n_...truncated ({len(content)} chars)_"
        return True, content
    except Exception as e: return False, f"❌ Error: {e}"

# ══ GITHUB API — BRANCHES ══════════════════════════════════════════════════════
def github_list_branches(token, repo_url):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, [], "❌ Invalid GitHub URL."
        r = requests.get(f"https://api.github.com/repos/{m.group(1)}/branches?per_page=100", headers=_H(token), timeout=30)
        if r.status_code != 200: return False, [], f"❌ GitHub error: `{r.json().get('message', '')}`"
        return True, [b["name"] for b in r.json()], ""
    except Exception as e: return False, [], f"❌ Error: {e}"

def github_create_branch(token, repo_url, new_branch, from_branch="main"):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        rp = m.group(1)
        r = requests.get(f"https://api.github.com/repos/{rp}/git/ref/heads/{from_branch}", headers=_H(token), timeout=30)
        if r.status_code != 200: return False, f"❌ Source branch `{from_branch}` not found."
        sha = r.json()["object"]["sha"]
        r2 = requests.post(f"https://api.github.com/repos/{rp}/git/refs", headers=_H(token),
                           json={"ref": f"refs/heads/{new_branch}", "sha": sha}, timeout=30)
        if r2.status_code in (200, 201): return True, f"✅ Branch `{new_branch}` created from `{from_branch}`"
        err = r2.json().get("message", r2.text[:200])
        return False, f"❌ {'Branch already exists.' if 'already exists' in err.lower() else f'GitHub error: `{err}`'}"
    except Exception as e: return False, f"❌ Error: {e}"

def github_delete_branch(token, repo_url, branch):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        r = requests.delete(f"https://api.github.com/repos/{m.group(1)}/git/refs/heads/{branch}", headers=_H(token), timeout=30)
        if r.status_code == 204: return True, f"✅ Branch `{branch}` deleted."
        return False, f"❌ GitHub error: `{r.json().get('message', r.text[:200])}`"
    except Exception as e: return False, f"❌ Error: {e}"

def github_merge_branch(token, repo_url, base, head, msg="Merge via bot"):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        r = requests.post(f"https://api.github.com/repos/{m.group(1)}/merges", headers=_H(token),
                          json={"base": base, "head": head, "commit_message": msg}, timeout=30)
        if r.status_code in (200, 201): return True, f"✅ Merged `{head}` → `{base}` successfully!"
        if r.status_code == 204: return True, "ℹ️ Already up-to-date."
        if r.status_code == 409: return False, "❌ Merge conflict — resolve manually."
        return False, f"❌ GitHub error: `{r.json().get('message', r.text[:200])}`"
    except Exception as e: return False, f"❌ Error: {e}"

# ══ GITHUB API — COLLABORATORS ════════════════════════════════════════════════
def github_list_collaborators(token, repo_url):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        r = requests.get(f"https://api.github.com/repos/{m.group(1)}/collaborators", headers=_H(token), timeout=30)
        if r.status_code != 200: return False, f"❌ GitHub error: `{r.json().get('message', '')}`"
        collabs = r.json()
        if not collabs: return True, "👥 No collaborators found."
        return True, "👥 **Collaborators:**\n" + "\n".join(f"• `{c['login']}` — {c.get('role_name','member')}" for c in collabs)
    except Exception as e: return False, f"❌ Error: {e}"

def github_add_collaborator(token, repo_url, username, permission="push"):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        r = requests.put(f"https://api.github.com/repos/{m.group(1)}/collaborators/{username}",
                         headers=_H(token), json={"permission": permission}, timeout=30)
        if r.status_code in (200, 201, 204): return True, f"✅ Invited `{username}` as collaborator ({permission})."
        return False, f"❌ GitHub error: `{r.json().get('message', r.text[:200])}`"
    except Exception as e: return False, f"❌ Error: {e}"

def github_remove_collaborator(token, repo_url, username):
    try:
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        if not m: return False, "❌ Invalid GitHub URL."
        r = requests.delete(f"https://api.github.com/repos/{m.group(1)}/collaborators/{username}", headers=_H(token), timeout=30)
        if r.status_code == 204: return True, f"✅ Removed `{username}` from collaborators."
        return False, f"❌ GitHub error: `{r.json().get('message', r.text[:200])}`"
    except Exception as e: return False, f"❌ Error: {e}"

# ══ GITHUB API — GISTS ════════════════════════════════════════════════════════
def github_list_gists(token):
    try:
        r = requests.get("https://api.github.com/gists?per_page=30", headers=_H(token), timeout=30)
        if r.status_code != 200: return False, [], f"❌ GitHub error: `{r.json().get('message', '')}`"
        return True, r.json(), ""
    except Exception as e: return False, [], f"❌ Error: {e}"

def github_create_gist(token, filename, content, description="", public=True):
    try:
        r = requests.post("https://api.github.com/gists", headers=_H(token),
                          json={"description": description, "public": public, "files": {filename: {"content": content}}}, timeout=30)
        if r.status_code in (200, 201):
            url = r.json().get("html_url", "")
            return True, f"✅ Gist created! ({'🔓 Public' if public else '🔒 Secret'})\n🔗 {url}"
        return False, f"❌ GitHub error: `{r.json().get('message', r.text[:200])}`"
    except Exception as e: return False, f"❌ Error: {e}"

def github_delete_gist(token, gist_id):
    try:
        r = requests.delete(f"https://api.github.com/gists/{gist_id}", headers=_H(token), timeout=30)
        if r.status_code == 204: return True, "✅ Gist deleted."
        return False, f"❌ GitHub error: `{r.json().get('message', r.text[:200])}`"
    except Exception as e: return False, f"❌ Error: {e}"

# ══ GITHUB API — PROFILE ══════════════════════════════════════════════════════
def github_get_profile(token):
    try:
        r = requests.get("https://api.github.com/user", headers=_H(token), timeout=30)
        if r.status_code != 200: return False, {}, f"❌ GitHub error: `{r.json().get('message', '')}`"
        return True, r.json(), ""
    except Exception as e: return False, {}, f"❌ Error: {e}"

def github_update_profile(token, name=None, bio=None, location=None, blog=None, twitter=None):
    try:
        payload = {}
        if name     is not None: payload["name"]             = name
        if bio      is not None: payload["bio"]              = bio
        if location is not None: payload["location"]         = location
        if blog     is not None: payload["blog"]             = blog
        if twitter  is not None: payload["twitter_username"] = twitter
        if not payload: return False, "❌ Nothing to update."
        r = requests.patch("https://api.github.com/user", headers=_H(token), json=payload, timeout=30)
        if r.status_code == 200: return True, f"✅ Profile updated: {', '.join(payload.keys())}"
        return False, f"❌ GitHub error: `{r.json().get('message', r.text[:200])}`"
    except Exception as e: return False, f"❌ Error: {e}"
