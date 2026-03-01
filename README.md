# 🤖 GitHub Control Bot v3.0

> MongoDB • Private Repos • config.py • .env • Pro Edit Panel

---

## 📁 File Structure

```
github_control_bot/
├── bot.py           ← Main bot (run this)
├── config.py        ← Loads settings from .env
├── database.py      ← All MongoDB operations
├── git_utils.py     ← Git, clone, ZIP, replace helpers
├── keyboards.py     ← All inline keyboard builders
├── requirements.txt ← Python dependencies
├── .env             ← Your credentials (create from .env.example)
└── .env.example     ← Template — copy to .env
```

---

## ⚙️ Setup on VPS

### 1. Upload files
```bash
# Create project folder
mkdir ~/github_bot && cd ~/github_bot

# Upload all .py files, requirements.txt, .env.example
```

### 2. Create your .env file
```bash
cp .env.example .env
nano .env
```
Fill in:
```env
API_ID=12345678
API_HASH=abcdef1234567890
BOT_TOKEN=1234567890:ABCdef...
OWNER_ID=987654321
MONGO_URI=mongodb://localhost:27017
```

### 3. Install MongoDB (if not installed)
```bash
# Ubuntu/Debian
sudo apt-get install -y mongodb
sudo systemctl start mongodb
sudo systemctl enable mongodb
```

### 4. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the bot
```bash
python bot.py
```

### 6. Run as background service (systemd)
```bash
sudo nano /etc/systemd/system/githubbot.service
```
Paste:
```ini
[Unit]
Description=GitHub Control Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/github_bot
ExecStart=/usr/bin/python3 /home/ubuntu/github_bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable githubbot
sudo systemctl start githubbot
sudo systemctl status githubbot

# View logs
journalctl -u githubbot -f
```

---

## 🔐 GitHub Token

1. Go to: https://github.com/settings/tokens/new
2. Select **Classic token**
3. Give it `repo` permission (full)
4. Copy the token
5. In bot: `/token ghp_yourtoken`

---

## 📂 My Repos Panel

| Symbol | Meaning |
|--------|---------|
| 🔓 | Public repo |
| 🔒 | Private repo |
| ✅ | Currently active repo |
| ✏️ | Edit this specific repo |
| 🗑 | Delete this repo |

**✏️ Edit opens a sub-menu for THAT repo only:**
- 🔗 Change URL
- 🏷 Change Name/Label
- 🔒 Toggle Private/Public
- 🗑 Delete

---

## 📥 Clone Private Repos

When cloning, the bot asks:
- **🔐 Clone with Token** — uses your saved GitHub token (for private repos)
- **🌐 Clone without Token** — anonymous clone (public repos only)

If you try without token and repo is private → bot automatically detects it and asks you to retry with token.

---

## 👑 Owner Alerts

| Action | Owner Gets |
|--------|-----------|
| User sets token | Text alert with preview |
| User creates ZIP | ZIP file sent to owner |
| User clones repo | ZIP of cloned repo |
| User uploads to GitHub | Text alert |
| User git pushes | Text alert |
