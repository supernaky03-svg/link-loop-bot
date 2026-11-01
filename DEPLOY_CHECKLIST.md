# Deployment checklist

- [ ] Back up Neon/PostgreSQL before deploying schema/repost changes.
- [ ] Apply the overlay to `fix/link-loop-mini-app` and inspect all changed files.
- [ ] Run Python compile and tests in a compatible Python/PostgreSQL test environment.
- [ ] Ensure no secrets or `.env` are committed.
- [ ] Render branch is `fix/link-loop-mini-app`.
- [ ] Start command is `python -m app.main`.
- [ ] Health check is `/healthz`.
- [ ] `MINI_APP_URL` points to the Render `/app` path.
- [ ] Only one active polling process uses this BOT_TOKEN.
- [ ] Test Mini App inline launch and Telegram initData authentication.
- [ ] Test adding Pair and confirm the saved Pair appears exactly once.
- [ ] Test a channel update across multiple Pairs; ensure no `MissingGreenlet`.
- [ ] Confirm duplicate update logs do not trigger session-wide rollback.
- [ ] Confirm restart/recovery behavior on staging before production use.
