# Termux commands — apply, test, commit and push

This ZIP is a patch overlay, not the full upstream repository. Clone the public repository first. The repository's `link-loop-bot-fixed/` folder contains the repost-engine fixes; this ZIP adds Mini App and its integration scripts.

## 1. Prepare Termux

```bash
pkg update && pkg upgrade -y
pkg install git python unzip gh -y
termux-setup-storage
```

Copy the ZIP to `/sdcard/Download/`.

## 2. Clone and apply

```bash
cd ~
git clone https://github.com/supernaky03-svg/link-loop-bot.git
cd link-loop-bot
unzip -o /sdcard/Download/link-loop-bot-full-fix-miniapp-v2.zip -d .
python apply_link_loop_all_fixes.py
```

## 3. Install and test

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m compileall -q app tests
pytest -q
```

A live test still requires your own Telegram token and PostgreSQL database. The ZIP contains no credentials.

## 4. Render setting

Add this environment variable in Render using the actual service URL:

```text
MINI_APP_URL=https://YOUR-RENDER-SERVICE.onrender.com/app
```

Keep current `BOT_TOKEN`, `ADMIN_IDS`, `DATABASE_URL`, Render start command `python -m app.main`, and health path `/healthz`.

**Before deploying:** back up Neon/PostgreSQL and review `link-loop-bot-fixed/APPLY_PATCH.md` and `link-loop-bot-fixed/BUG_FIXES.md`. The existing hotfix overlay modifies schema and removes duplicate loop-origin rows.

## 5. Commit on a feature branch

```bash
git switch -c fix/link-loop-mini-app
git status --short
# Confirm .env, tokens, and database URLs are NOT shown.
git add app tests .env.example
git commit -m "Fix async repost engine and add Telegram Mini App"
```

## 6. Authenticate and push

Use GitHub CLI browser/device login so the token is not placed in shell history:

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
gh auth status
git push -u origin fix/link-loop-mini-app
```

Then open a Pull Request from `fix/link-loop-mini-app` into `main`, review CI and the diff, and merge. Do not force-push.

## 7. Post-deployment checks

- Open the bot and use **Open Mini App**.
- Check the signed Telegram identity and user-only pair visibility.
- Test create, edit style/order, Movie Rule, remove and permission recheck.
- As admin, test dashboard, ban/unban, limits and status report.
- Confirm `/healthz` still returns HTTP 200 with `{"ok": true}`.
