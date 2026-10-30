# v3 hotfix changelog

## Root-cause fix — SQLAlchemy MissingGreenlet during Pair creation

The traceback pinpoints `Repository.create_pair()` at `pair.channels.append(...)`. A newly constructed SQLAlchemy `Pair` had an unset/unloaded `channels` relationship. Even though the mapped relationship uses `lazy="selectin"`, a new instance does not automatically have its collection initialized. Accessing `.append()` after `flush()` could therefore try an implicit synchronous lazy-load and raise `MissingGreenlet` with AsyncSession/asyncpg.

The new Pair constructor now explicitly receives `channels=[]` before it is added/flushed. That makes the collection an initialized in-memory list and prevents the implicit database IO. Existing inactive pairs are fetched with `selectinload(Pair.channels)` and their collection is explicitly reset before replacement.

## Prevent the handler registration regression

The upstream repost-fix overlay contains an empty `app/bot/handlers/__init__.py`, while `app.main` imports `register_handlers`. The apply script now restores all router registrations after copying that overlay, preventing the earlier Render `ImportError` from returning. The menu router is deliberately registered before state-wide text-input routers, so the Mini App reply-keyboard text is not mistakenly treated as a channel list during an unfinished Pair flow.

## Pair confirmation failure handling

On a failed DB operation, the handler explicitly rolls back the AsyncSession. It keeps the FSM in the confirmation step and preserves the confirm keyboard, allowing a transient database failure to be retried. The full traceback remains logged for diagnosis.

## Mini App launch UX

The Reply Keyboard now sends plain text `📱 Mini App ဖွင့်မယ်` / `📱 Open Mini App`. The bot responds with a separate Inline Keyboard `web_app` button. Pressing the Inline Button opens the Telegram Mini App at `MINI_APP_URL`.

## Files changed by apply script

- `app/bot/handlers/__init__.py`
- `app/db/repository.py`
- `app/bot/handlers/pair_add.py`
- `app/bot/keyboards/reply.py`
- `app/bot/keyboards/inline.py`
- `app/bot/handlers/menu.py`
- `tests/test_pair_channels_initialization.py`

The all-in-one apply script also reapplies the previously supplied repost-engine and Mini App overlay files.
