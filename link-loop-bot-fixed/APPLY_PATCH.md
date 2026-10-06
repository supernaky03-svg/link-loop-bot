# link-loop-bot fixed overlay

This archive is a **source overlay** for `supernaky03-svg/link-loop-bot` `main`.
It contains only the files changed for the bug-fix pass; unchanged upstream files must stay in place.

## Apply

1. Back up the existing repo.
2. Extract this ZIP at the repository root, preserving the `app/` and `tests/` paths.
3. Keep the existing `requirements.txt`, deployment files, handlers, keyboards, locales, etc. that are not in this archive.
4. Restart the bot once so `app/db/session.py:init_db()` applies the additive database migration.
5. Run the existing project test suite and the included regression tests.

No new Python dependency was intentionally introduced.

## Database migration notes

The startup migration:
- adds stored Telegram entities / caption entities / inline keyboard JSON to `post_items`;
- adds persisted loop delivery IDs and footer readiness to `loop_states`;
- replaces the old loop-step uniqueness with per-created-message event tracking;
- adds a one-time origin claim for a `(pair, source chat, source message)`;
- removes duplicate historical `loop_states` rows before the new origin index is created.

Back up PostgreSQL before deploying schema changes.

## Validation

The offline regression suite included in this overlay passes 6/6 tests. The build environment used for this patch could not reach GitHub and did not have `aiogram`/`asyncpg` installed, so a live Telegram/PostgreSQL integration run was not possible here.
