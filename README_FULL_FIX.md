# Link Loop Bot — Reliability fix + Telegram Mini App overlay

This ZIP is an integration overlay for the public repository `supernaky03-svg/link-loop-bot`; it is not a standalone full-source export. Clone the public repository first. The current `main` already contains `link-loop-bot-fixed/`, a separate repost-engine hotfix overlay. `apply_link_loop_all_fixes.py` applies that overlay and then integrates this Mini App.

## Included changes

- The existing repost-engine hotfix overlay: duplicate-origin protection, safer fan-out failure handling, post-cache/origin safeguards, album collector fixes, loop/footer recovery, message entity/inline-keyboard preservation and idempotency safeguards.
- Explicit SQLAlchemy `selectin` loading on `User.pairs`, targeting the `MissingGreenlet` lazy-load failure.
- Telegram Mini App served by the existing aiohttp service and existing Render port.
- Telegram `initData` HMAC signature and auth-date verification on every API request.
- User-scoped APIs: list/create/update/remove pairs, Random/By Order, Movie Rule, channel permission recheck, language and contact/help.
- Admin APIs: dashboard, ban/unban, per-user limits, default limits, user limit and status report.
- Bot keyboard launch button, enabled only when `MINI_APP_URL` is set to a public HTTPS URL.

The Mini App uses the same PostgreSQL tables and repository/services as the bot. It does not run a second repost engine; channel posts continue to be processed by the bot.

## Apply

Extract this ZIP at the root of a clean clone of the public repository and run:

```bash
python apply_link_loop_all_fixes.py
```

See `TERMUX_COMMIT.md` for Termux clone, apply, test, commit and push commands.

## Safety

- ZIP does not contain the upstream base repository; clone `main` first.
- Before first deployment, back up Neon/PostgreSQL. The existing `link-loop-bot-fixed` overlay includes additive schema migrations and duplicate loop-origin cleanup.
- Configure `MINI_APP_URL=https://YOUR-RENDER-SERVICE.onrender.com/app` in Render.
- Never commit `.env`, `BOT_TOKEN`, `DATABASE_URL`, GitHub tokens or Render secrets.
- Production success requires the full test suite plus live Telegram/PostgreSQL testing; a local syntax/auth test is not proof of a live deployment.
