# Link Loop Bot — repost fixes + Mini App + Pair creation hotfix

This is an **integration overlay** for the public repository `supernaky03-svg/link-loop-bot`, not a standalone export of every upstream repository file. Clone the repository first, then extract this ZIP into the repository root.

## Included work

- Existing `link-loop-bot-fixed/` upstream repost-engine fixes (copied by the apply script). The upstream overlay contains an empty `app/bot/handlers/__init__.py`; this ZIP explicitly restores `register_handlers()` so the previous Render import error is not reintroduced.
- Telegram Mini App backend/UI, signed Telegram `initData` validation, user-scoped pair APIs, and admin functions.
- SQLAlchemy async eager-loading change for `User.pairs`.
- **Confirmed Pair 5 / MissingGreenlet fix:** new `Pair` objects are constructed with `channels=[]` before `flush()`. This initializes the ORM collection so `pair.channels.append(...)` cannot trigger an implicit lazy-load outside SQLAlchemy's async greenlet context.
- Failed Pair confirmation performs an AsyncSession rollback and leaves the confirmation keyboard available for a retry instead of leaving a failed transaction open.
- **Mini App launch UX:** Reply Keyboard button is plain text. Tapping it makes the bot send a second message with an Inline Keyboard `web_app` button; that Inline button launches the Mini App.
- Focused tests for Mini App authentication, `User.pairs` eager-loading and new `Pair.channels` initialization.

## Apply to existing Termux clone

1. Keep your existing clone and branch; do not delete the database or existing pairs.
2. Extract the ZIP into the root of `~/link-loop-bot` (merge/overwrite when prompted).
3. Run:

```bash
python apply_link_loop_all_fixes.py
python -m compileall -q app tests
python -m pytest -q tests/test_mini_app_auth.py
```

The full suite should be run in the Render build environment or a compatible Linux/Python environment with all `requirements.txt` dependencies installed. Termux Android may not have compatible prebuilt wheels for `pydantic-core` or `asyncpg`; do not upgrade Termux's system pip with `python -m pip install --upgrade pip`.

## Mini App URL

Set Render environment variable to the actual service URL:

```text
MINI_APP_URL=https://link-loop-bot.onrender.com/app
```

Keep `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_IDS`, `python -m app.main`, and `/healthz` as before. Do not commit secrets.

## Pair creation verification

After deploying, add one Pair using two test channels where the bot has admin + Post Messages permission. Verify:

1. Confirm returns Pair created.
2. `My Pairs` displays it.
3. Restart/redeploy does not create a duplicate Pair.
4. The Render log has no `MissingGreenlet` from `repository.py` at `pair.channels.append`.

The new ORM test proves that constructor-supplied `channels=[]` starts loaded; it is not a substitute for a live PostgreSQL/Telegram test.

## Important deployment safety

- Do not delete existing Pair rows or drop tables.
- Back up Neon/PostgreSQL before applying the existing repost-engine migration overlay; its existing migration removes duplicate loop-origin rows.
- Deploy one Render service/instance for this polling bot and do not run the same bot token on a second host simultaneously.
- `/healthz` returning 200 verifies the HTTP health route, not all Telegram/DB functions.
- Validate the feature branch diff before merging into `main`.
