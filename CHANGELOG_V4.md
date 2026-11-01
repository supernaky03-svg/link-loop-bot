# Link Loop Bot v4 hotfix

## Root cause addressed

The v3 Pair creation fix initializes `Pair.channels=[]`, addressing the `MissingGreenlet` raised by `pair.channels.append()` in `Repository.create_pair()`.

The new Render log exposed a second, related async ORM problem in channel-post fan-out:

- `Repository.mark_processed()` handled a duplicate `ProcessedUpdate` by catching `IntegrityError` and calling `AsyncSession.rollback()`.
- `Repository.create_loop_state()` did the same for an already-claimed `(pair_id, origin_chat_id, origin_message_id)`.
- `Repository.save_loop_event()` also rolled back on duplicate loop events.

A SQLAlchemy rollback expires persistent ORM instances in the session, including the `Pair` objects returned by `active_pairs_by_chat()`. `expire_on_commit=False` does not prevent rollback expiration. The next `pair.is_paused` read then tries to reload an expired scalar attribute using implicit IO, producing `MissingGreenlet`.

## v4 change

Replace the three duplicate-detection write paths with PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` and `RETURNING` where the caller needs to know whether it won the claim. Duplicate updates remain idempotent, but the shared AsyncSession is no longer rolled back for expected uniqueness conflicts.

Files added/updated by this overlay:
- `apply_loop_dedupe_rollback_fix.py`
- `tests/test_loop_dedupe_rollback_safety.py`
- `apply_link_loop_all_fixes.py` invokes the new hotfix after the v3 patches.

The v3 features remain included: Mini App, Telegram initData verification, handler registration, Pair `channels=[]` initialization, and the Reply Keyboard -> Inline Web App Button launch flow.

## Validation boundary

The patch script is designed for the repository layout shown in the GitHub branch. Run compile/tests against the full checkout and verify on a staging database before production rollout. No live Render or Telegram test is claimed by this package.
