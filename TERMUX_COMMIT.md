# Termux apply, test, commit, push

```bash
cd ~/link-loop-bot
git status --short
git switch fix/link-loop-mini-app
git pull --ff-only origin fix/link-loop-mini-app
unzip -o /sdcard/Download/link-loop-bot-full-fix-miniapp-v4.zip -d .
python apply_link_loop_all_fixes.py
python -m compileall -q app tests
python -m pytest -q tests/test_mini_app_auth.py
python -m pytest -q tests/test_handler_registration_export.py
python -m pytest -q tests/test_pair_channels_initialization.py
python -m pytest -q tests/test_loop_dedupe_rollback_safety.py
git diff --check
git status --short
```

If Termux cannot install native dependencies (`asyncpg`, `pydantic-core`, SQLAlchemy), do not run an unrestricted `pip install --upgrade pip` on Termux. Static compile can still be run, but tests that import SQLAlchemy require a compatible test environment. The static rollback-safety test itself needs only Python and pytest.

Inspect the diff and confirm no `.env`, Bot token, Database URL, or GitHub credentials are staged. Then:

```bash
git add app tests apply_link_loop_all_fixes.py apply_mini_app_patch.py \
  apply_pair_and_mini_launch_fix.py apply_loop_dedupe_rollback_fix.py \
  README_FULL_FIX.md TERMUX_COMMIT.md DEPLOY_CHECKLIST.md \
  CHANGELOG_V3.md CHANGELOG_V4.md PATCH_MANIFEST.json
git commit -m "Prevent async session expiry on duplicate repost claims"
git push origin fix/link-loop-mini-app
```

Deploy the feature branch to Render. Keep one active poller for this bot token.
