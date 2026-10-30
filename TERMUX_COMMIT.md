# Termux — apply, test, commit and push

This ZIP is an overlay on `supernaky03-svg/link-loop-bot`, not the entire upstream source tree. Use your existing clone when possible.

## 1. Prepare Termux

```bash
pkg update && pkg upgrade -y
pkg install git python unzip gh -y
termux-setup-storage
```

Do **not** run `python -m pip install --upgrade pip`; Termux manages its system pip package and blocks that operation.

## 2. Extract into the existing repository

Copy the ZIP to `/sdcard/Download/`, then:

```bash
cd ~/link-loop-bot
git switch fix/link-loop-mini-app
git pull --ff-only origin fix/link-loop-mini-app
unzip -o /sdcard/Download/link-loop-bot-full-fix-miniapp-v3.zip -d .
python apply_link_loop_all_fixes.py
```

The orchestrator reapplies the project's upstream repost-fix overlay, Mini App integration and this final Pair/keyboard hotfix. Review `git status` immediately afterward.

## 3. Checks

```bash
python -m compileall -q app tests
python -m pytest -q tests/test_mini_app_auth.py
# Requires SQLAlchemy to be installed in Termux; if it is not, run this test
# in Render/Linux rather than forcing native dependency builds on Android.
python -m pytest -q tests/test_pair_channels_initialization.py
python -m pytest -q tests/test_handler_registration_export.py
```

If SQLAlchemy is available, also run:

```bash
python -m pytest -q tests/test_async_relationship_loading.py
```

Termux Android may not have compatible wheels for native dependencies such as `pydantic-core` and `asyncpg`. If the full `requirements.txt` install fails, do not treat that as an application-code test failure; run the full test suite on compatible Linux/Render instead.

## 4. Review and commit

```bash
git diff --check
git status --short
```

Confirm that `.env`, bot tokens, database URLs and GitHub tokens are not staged. Then:

```bash
git add app tests .env.example apply_link_loop_all_fixes.py apply_mini_app_patch.py apply_pair_and_mini_launch_fix.py README_FULL_FIX.md TERMUX_COMMIT.md DEPLOY_CHECKLIST.md
git commit -m "Fix Pair async collection and Mini App launch"
```

## 5. Push

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
git push origin fix/link-loop-mini-app
```

If the branch already tracks origin, `git push` is also sufficient. Open/review the PR before merging.

## 6. Render

- Branch: `fix/link-loop-mini-app`
- Start command: `python -m app.main`
- Environment: `MINI_APP_URL=https://link-loop-bot.onrender.com/app`
- One service instance only for this bot token.

After deploy, test `/start`, Mini App reply-keyboard → inline-button launch, My Pairs, add Pair, and real repost delivery.
