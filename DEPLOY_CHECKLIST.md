# Deployment checklist

## Database / async SQLAlchemy
- [ ] `User.pairs.property.lazy == "selectin"`.
- [ ] `Pair.channels` and `Pair.user` remain eagerly loaded.
- [ ] Back up Neon/PostgreSQL before the migration.
- [ ] Test migrations on a staging database before production.

## Bot / repost worker
- [ ] `/start`, `/status`, `/ban`, `/unban`.
- [ ] Pair creation/removal and style editing.
- [ ] Random route keeps source channel first; By Order follows stored order.
- [ ] Movie Rule selects previous cached post, not the video trigger.
- [ ] Albums collect fully; bot-created reposts never re-enter source cache.
- [ ] Failed intermediate hops do not send downstream with invalid footer ancestry.
- [ ] Footer recovery works after restart; failures do not become `done`.
- [ ] Formatting, hidden links and inline keyboards survive where Telegram supports them.

## Mini App
- [ ] Opens via Telegram Web App button on HTTPS.
- [ ] Invalid/tampered/expired initData receives 401.
- [ ] API identity comes only from verified initData.
- [ ] User endpoints cannot read/update another user's pairs.
- [ ] Non-admin accounts receive 403 for admin endpoints.
- [ ] Pair create/edit/remove, Movie Rule, language and permission recheck work.
- [ ] Admin dashboard, ban/unban, limits and report work.
- [ ] Telegram light/dark theme is respected.
- [ ] `/healthz` continues returning 200.

## Render
- [ ] Set `MINI_APP_URL=https://<render-service>.onrender.com/app`.
- [ ] Retain existing secret environment variables.
- [ ] Start command remains `python -m app.main`.
