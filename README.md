# Telegram Channel Link Loop Bot

Production-ready Telegram channel link loop bot using **aiogram v3**, **async SQLAlchemy**, **PostgreSQL/Neon**, and a small **aiohttp health endpoint** for Render + UptimeRobot.

## 1. Architecture summary

The bot uses one Telegram Bot Token and watches `channel_post` updates from channels where the bot is admin. Users create numbered channel pairs. Each pair contains 2 or more channels, default maximum 6. When a post appears in a channel that belongs to an active pair, the bot builds a route and reposts the cached post unit through the route.

Main flow:

1. `channel_posts.py` receives channel posts.
2. `AlbumCollector` waits for album items with the same `media_group_id` and saves them as one post unit.
3. `movie_rule_service.py` saves each post unit into PostgreSQL and keeps only the latest 50 units per channel.
4. `repost_service.py` starts or continues a loop.
5. `loop_states`, `loop_events`, and `processed_updates` prevent duplicate processing and infinite independent loops.
6. `permissions.py` listens to `my_chat_member` updates, pauses pairs when permission is removed, reports to admin group, and reactivates pairs after admin permission is restored.

Important Telegram Bot API limitation: a bot cannot join private channels by invite link like a user account. For private channels, add the bot as admin first, then provide the numeric `-100...` channel ID. Public `@username` and `https://t.me/username` links are supported.

## 2. Complete file structure

```text
app/
  main.py
  config.py
  health.py
  db/
    __init__.py
    base.py
    models.py
    repository.py
    session.py
  bot/
    __init__.py
    loader.py
    middlewares.py
    keyboards/
      __init__.py
      inline.py
      reply.py
    handlers/
      __init__.py
      admin.py
      channel_posts.py
      menu.py
      pair_add.py
      pair_edit.py
      pair_remove.py
      permissions.py
      start.py
    services/
      __init__.py
      album_service.py
      channel_service.py
      flow_message.py
      language_service.py
      link_service.py
      movie_rule_service.py
      pair_service.py
      permission_service.py
      report_service.py
      repost_service.py
    states/
      __init__.py
      pair_states.py
    locales/
      __init__.py
      en.py
      my.py
tests/
  __init__.py
  test_parsers.py
.env.example
.gitignore
README.md
render.yaml
requirements.txt
```

## 3. Database setup

This project uses auto-create table logic:

```python
await init_db()
```

On startup, SQLAlchemy creates these tables if missing:

- `users`
- `settings`
- `pairs`
- `pair_channels`
- `post_units`
- `post_items`
- `loop_states`
- `loop_events`
- `processed_updates`
- `admin_reports`

For a larger commercial deployment, replace auto-create with Alembic migrations later. The current version is ready for a small/medium Render + Neon deployment.

## 4. Neon DB setup guide

1. Go to Neon and create a new PostgreSQL project.
2. Choose a region close to your Render region when possible.
3. Open **Connection Details**.
4. Copy the pooled or direct connection string.
5. Make sure it looks like:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require
```

The code automatically converts it to `postgresql+asyncpg://...` and moves `sslmode=require` into asyncpg SSL connect arguments.

## 5. Render deployment guide

### Option A: Manual Render setup

1. Push this project to GitHub.
2. Render → New → Web Service.
3. Select your GitHub repo.
4. Runtime: Python.
5. Build command:

```bash
pip install -r requirements.txt
```

6. Start command:

```bash
python -m app.main
```

7. Add environment variables from `.env.example`.
8. Set health check path:

```text
/healthz
```

9. Deploy.

### Option B: render.yaml

This repo includes `render.yaml`:

```yaml
services:
  - type: web
    name: channel-link-loop-bot
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python -m app.main
    healthCheckPath: /healthz
    autoDeploy: true
```

Render can detect this blueprint.

## 6. Required environment variables

```env
BOT_TOKEN=123456:ABCDEF
ADMIN_IDS=123456789,987654321
REPORT_GROUP_ID=-5159311101
DATABASE_URL=postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require
DEFAULT_PAIR_LIMIT=10
DEFAULT_CHANNEL_PER_PAIR_LIMIT=6
DEFAULT_LANGUAGE=en
USER_LIMIT=0
LOG_LEVEL=INFO
HEALTH_HOST=0.0.0.0
PORT=10000
HEALTH_PATH=/healthz
POST_CACHE_LIMIT_PER_CHANNEL=50
ALBUM_COLLECT_DELAY_SECONDS=2
BANNED_SILENT=true
ADMIN_CONTACT=@mnsm6003
```

`USER_LIMIT=0` means unlimited users.

## 7. UptimeRobot setup guide

1. UptimeRobot → Add New Monitor.
2. Type: HTTP(s).
3. URL:

```text
https://YOUR-RENDER-APP.onrender.com/healthz
```

4. Interval: 5 minutes.
5. Save.

Expected response:

```json
{"ok": true}
```

## 8. Admin command usage

### `/status`

Shows all registered users:

```text
────────── User 1 ──────────
Username: @example
User ID: 123456789
Pair Count: 2
Total Channels: 8
Banned: No
Pair Limit: 10
Channel Per Pair Limit: 6
```

### `/ban user_id_or_username`

```text
/ban 123456789
/ban @example
```

Banned normal users receive no response.

### `/unban user_id_or_username`

```text
/unban 123456789
/unban @example
```

### `/set_pair_limit user_id count`

```text
/set_pair_limit 123456789 20
```

### `/set_default_pair_limit count`

```text
/set_default_pair_limit 10
```

### `/set_ch_p_pair user_id count`

```text
/set_ch_p_pair 123456789 8
```

### `/set_default_ch_p_pair count`

```text
/set_default_ch_p_pair 6
```

### `/user_limit count`

```text
/user_limit 100
```

If total registered users reaches this number, new users receive no response. Existing users continue unless banned.

## 9. User guide — English

### First setup

1. Start the bot with `/start`.
2. Add the bot as admin in every channel you want to use.
3. Give the bot **Post Messages** permission.
4. For public channels, you can use `@username` or `https://t.me/username`.
5. For private channels, add the bot as admin first and use numeric `-100...` chat ID.

### Add Pair

Menu → `➕ Add Pair`

Steps:

1. Send pair number or press Auto.
2. Choose repost style:
   - Random
   - By Order
3. Send channel links/IDs.
4. Choose Movie Rule ON/OFF.
5. Confirm.

### Random style

If pair contains A, B, C and source is A:

- A → B → C, or
- A → C → B

The destination order is shuffled each loop.

### By Order style

If order is A=1, B=2, C=3:

- Source is first.
- Other channels are sorted by order number.

Examples:

- A source: A → B → C
- B source: B → A → C
- C source: C → A → B

### Movie Rule

Movie Rule OFF:

- Every post is looped.

Movie Rule ON:

- The bot reacts only when a video post appears.
- It does not loop the video itself.
- It loops the post immediately above that video if that previous post was already captured by the bot.
- Albums are reposted as albums.

## 10. User guide — Myanmar

### စတင်အသုံးပြုနည်း

1. Bot ကို `/start` လုပ်ပါ။
2. အသုံးပြုမည့် channel တိုင်းတွင် bot ကို admin ထည့်ပါ။
3. **Post Messages** permission ပေးပါ။
4. Public channel ဆိုလျှင် `@username` သို့မဟုတ် `https://t.me/username` သုံးနိုင်သည်။
5. Private channel ဆိုလျှင် bot ကို admin အရင်ထည့်ပြီး `-100...` chat ID ကို သုံးပါ။

### Pair ထည့်နည်း

Menu → `➕ Pair ထည့်မယ်`

အဆင့်များ:

1. Pair number ပို့ပါ သို့မဟုတ် Auto နှိပ်ပါ။
2. Repost style ရွေးပါ:
   - Random
   - အစဉ်လိုက်
3. Channel links/IDs များပို့ပါ။
4. Movie Rule ON/OFF ရွေးပါ။
5. အတည်ပြုပါ။

### Random style

A, B, C ဆိုလျှင် A မှ post တက်လာသောအခါ:

- A → B → C သို့မဟုတ်
- A → C → B

စနစ်က loop တစ်ကြိမ်တိုင်း destination order ကို random လုပ်သည်။

### အစဉ်လိုက် style

Order သည် A=1, B=2, C=3 ဖြစ်လျှင်:

- Source channel ကို အရင်ထားမည်။
- ကျန် channel များကို order number အတိုင်းစီမည်။

ဥပမာ:

- A source: A → B → C
- B source: B → A → C
- C source: C → A → B

### Movie Rule

Movie Rule OFF:

- Post တိုင်း loop ပတ်မည်။

Movie Rule ON:

- Video post တက်လာမှသာ bot အလုပ်လုပ်မည်။
- Video post ကိုယ်တိုင်ကို loop မပတ်ပါ။
- အဲဒီ video အပေါ်က post ကို bot cache ထဲရှိပါက loop ပတ်မည်။
- Album ဖြစ်လျှင် album အတိုင်း ပြန်တင်မည်။

## 11. Manual test checklist

### Basic startup

- [ ] `python -m app.main` starts without syntax/import error.
- [ ] `/healthz` returns 200 OK.
- [ ] Tables are created in Neon.
- [ ] `/start` shows reply keyboard.

### Language

- [ ] Change language to English.
- [ ] Change language to Myanmar.
- [ ] Main menu button text changes.

### Add Pair

- [ ] Auto pair number works.
- [ ] Existing pair number is rejected.
- [ ] Pair limit is enforced.
- [ ] Channel count below 2 is rejected.
- [ ] Channel count above limit is rejected.
- [ ] Duplicate channels are rejected.
- [ ] Missing admin permission shows missing list.
- [ ] Recheck works after permission is fixed.
- [ ] Confirm saves pair.

### Remove Pair

- [ ] Select pair.
- [ ] Confirmation shows details.
- [ ] Confirm marks pair inactive.
- [ ] Removed pair no longer triggers admin reports.

### Edit Repost Style

- [ ] Random style saves.
- [ ] By Order asks for order.
- [ ] Invalid order is rejected.
- [ ] Valid order saves.

### Edit Movie Rule

- [ ] ON saves.
- [ ] OFF saves.

### Link loop

- [ ] A text post in A loops to B then C.
- [ ] Footer on B uses A channel/post link.
- [ ] Footer on C uses B channel/post link.
- [ ] Duplicate Telegram updates do not duplicate posts.
- [ ] Bot-created post does not start a new independent loop.

### Album

- [ ] 2-photo album is cached as one post unit.
- [ ] Album reposts via `sendMediaGroup`.
- [ ] Footer is attached to first media item.
- [ ] Album with more than 10 items is split safely.

### Movie Rule

- [ ] OFF loops all posts.
- [ ] ON ignores normal photo/text posts.
- [ ] ON reacts to video post.
- [ ] ON loops previous cached post, not the video.
- [ ] Previous album is looped as album.
- [ ] Missing previous post logs warning and does not crash.

### Permission monitoring

- [ ] Removing bot admin permission pauses active pairs using that channel.
- [ ] Report is sent to `REPORT_GROUP_ID`.
- [ ] User is notified.
- [ ] Restoring admin with Post Messages permission reactivates pairs if all channels are OK.

### Admin commands

- [ ] `/status` shows all users.
- [ ] `/ban` blocks user.
- [ ] `/unban` restores user.
- [ ] `/set_pair_limit` works.
- [ ] `/set_default_pair_limit` works.
- [ ] `/set_ch_p_pair` works.
- [ ] `/set_default_ch_p_pair` works.
- [ ] `/user_limit` blocks new users after limit.

## 12. Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill .env values
export $(grep -v '^#' .env | xargs)
python -m app.main
```

On Windows PowerShell, set env vars manually or use your hosting panel.

## 13. Notes for production scaling

This project is safe for one Render instance. The album collector is in-memory, so do not run multiple replicas without moving album buffering to Redis or DB. For a high-traffic paid bot, add Alembic migrations, Redis locks, and webhook mode.
