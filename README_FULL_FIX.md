# Link Loop Bot — Full Fix + Mini App v4

This ZIP is an overlay for `supernaky03-svg/link-loop-bot`, not a standalone full repository.

## What it fixes

- Existing repost reliability overlay from `link-loop-bot-fixed/`.
- `User.pairs` eager loading and New Pair `channels=[]` initialization to avoid async lazy-load `MissingGreenlet` errors.
- Empty `app.bot.handlers` export (`register_handlers`) from the upstream overlay.
- Mini App API/UI and Telegram initData authentication.
- Reply Keyboard Mini App item is a normal text button; pressing it produces an inline `web_app` button which launches the Mini App.
- Expected uniqueness conflicts during repost processing use PostgreSQL `ON CONFLICT DO NOTHING` rather than `AsyncSession.rollback()`. This prevents rollback from expiring already-loaded `Pair` objects that are subsequently read in `channel_posts.py`.

## Apply

1. Back up the PostgreSQL/Neon database.
2. Download this ZIP to Termux Downloads.
3. From the repository checkout, switch to the intended feature branch and pull it.
4. Extract the ZIP into the repository root.
5. Run `python apply_link_loop_all_fixes.py`.
6. Run compile/tests as listed in `TERMUX_COMMIT.md`.
7. Inspect `git diff` and ensure no secrets or `.env` file are staged.
8. Commit and push the branch, then deploy that branch to Render.

The apply script requires the repository's `link-loop-bot-fixed/app` and `link-loop-bot-fixed/tests` overlay folder, which exists in the target upstream repository. If it is missing, stop and check the branch instead of applying a partial patch.

## Render

- Start command: `python -m app.main`
- Health check path: `/healthz`
- `MINI_APP_URL=https://YOUR-SERVICE.onrender.com/app`
- Keep one active Render instance/poller for this bot token. Do not run the same token with polling on another host.

## Validation

A successful syntax compile and static/unit test run are not equivalent to a live Telegram/PostgreSQL test. Verify: Mini App launch, add Pair, My Pairs, source-channel fan-out, duplicate update handling, and restart recovery on a staging copy before treating the deployment as production-ready.
