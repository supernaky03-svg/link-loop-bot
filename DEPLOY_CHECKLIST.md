# Deploy Checklist — Link Loop Bot v3

## Before push
- [ ] Extract overlay into the existing `link-loop-bot` clone.
- [ ] Run `python apply_link_loop_all_fixes.py` successfully.
- [ ] `python -m compileall -q app tests` passes.
- [ ] Mini App auth test passes.
- [ ] Pair collection initialization test passes.
- [ ] `git diff --check` passes.
- [ ] No `.env`, tokens, or database credentials staged.

## Render configuration
- [ ] Deploy branch `fix/link-loop-mini-app`.
- [ ] Start command is `python -m app.main`.
- [ ] `MINI_APP_URL=https://link-loop-bot.onrender.com/app` (actual HTTPS URL).
- [ ] One Render service/instance is polling this token.
- [ ] Neon/PostgreSQL backup taken before schema migrations.

## Live tests
- [ ] `/healthz` returns 200.
- [ ] `/app` loads inside Telegram.
- [ ] Reply Keyboard Mini App action produces an Inline Web App button.
- [ ] Inline button opens Mini App.
- [ ] Existing four Pairs remain visible and unchanged.
- [ ] Fifth Pair can be created and appears in My Pairs.
- [ ] No `MissingGreenlet` in `add_pair confirm` log.
- [ ] Pair repost works end-to-end with bot admin/Post Messages permissions.
- [ ] No persistent `TelegramConflictError` after deploy has settled.
