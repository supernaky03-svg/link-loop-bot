Deplover- Thar Sett Nyan
Deplover county- Myanmar 

# Telegram Channel Link Loop Bot

Production-ready Telegram channel repost/link-loop bot built with **aiogram v3**, **async SQLAlchemy**, **PostgreSQL/Neon**, and an **aiohttp health endpoint** for Render + UptimeRobot.

This bot is designed for channel chains such as:

```text
A → B → C → D
A → C → B → D
D → A → B → C
```

The original post can come from **any channel inside the pair**. The source channel is always placed first in the route, and the other channels are ordered by the selected repost style.

---

## 1. Main Features

- Multi-user Telegram bot
- Pair-based channel loop system
- 2 or more channels per pair
- Default channel limit per pair: 6
- Public channel link support: `@username`, `https://t.me/username`
- Private channel support by numeric `-100...` chat ID
- Album/media group repost support
- Movie Rule support
- Always Random route mode
- By Order route mode
- Visible link removal from text/caption
- Delayed footer edit workflow
- Duplicate update protection
- Bot-created post loop protection
- Admin/user permission monitoring
- English and Myanmar language support
- Render deployment support
- UptimeRobot health check support

---

## 2. Important Telegram Limitation

This project uses a **Telegram Bot Token**, not a user account session.

A Telegram bot cannot join private channels by invite link like a normal Telegram user account. For private channels:

1. Add the bot to the private channel first.
2. Give the bot admin permission.
3. Give the bot **Post Messages** permission.
4. Use the numeric channel ID, for example:

```text
-1001234567890
```

For public channels, you can use:

```text
@channelusername
https://t.me/channelusername
```

---

## 3. New Repost Workflow

The new workflow does **not** wait for Channel 2's repost update before sending to Channel 3.

Instead, it works like this:

```text
1. Detect original post source channel.
2. Build route.
3. Send the original content to all target channels first.
4. Strip visible links during send.
5. Save created message IDs per channel.
6. Wait 15 seconds.
7. Edit the sent posts and add footer links.
```

This greatly reduces the bug where the repost reaches Channel 2 but does not continue to Channel 3.

---

## 4. Route Rules

Assume a pair contains these channels:

```text
A, B, C, D
```

### Source Channel Rule

The channel where the original post appears is always first.

Example:

```text
Original post appears in A
Route = A → other channels
```

If the original post appears in D:

```text
Route = D → other channels
```

---

## 5. Repost Styles

During pair creation, the user chooses one repost style.

### 5.1 Always Random

`Always Random` means every new post gets a fresh random route.

Example:

```text
First post source = A
Route = A → B → C → D

Second post source = A
Route = A → C → B → D

Third post source = D
Route = D → A → B → C
```

The source channel is never shuffled into the middle. It always stays first.

Only the remaining channels are shuffled.

### 5.2 By Order

`By Order` means the source channel is first, and the other channels follow the order saved by the user.

Example saved order:

```text
A = 1
B = 2
C = 3
D = 4
```

If source is A:

```text
A → B → C → D
```

If source is C:

```text
C → A → B → D
```

---

## 6. Footer Logic

The repost content always comes from the original source post.

The footer link always points to the previous channel in the route.

Example route:

```text
A → C → B → D
```

### Channel C footer

```text
channel join - Channel A link
ကြည့်ရန်လင့် - Channel A original post link
```

### Channel B footer

```text
channel join - Channel C link
ကြည့်ရန်လင့် - Channel C reposted post link
```

### Channel D footer

```text
channel join - Channel B link
ကြည့်ရန်လင့် - Channel B reposted post link
```

Important rule:

```text
Content source = original post
Footer source = previous channel's created post
```

Channel B does not reuse Channel C's reposted content.
Channel D does not reuse Channel B's reposted content.
All target channels receive the original post content.

---

## 7. Link Removal Rule

Visible links are removed from original text/caption before reposting.

Examples of visible links that should be removed:

```text
https://example.com
http://example.com
www.example.com
t.me/example
telegram.me/example
https://t.me/example
```

The bot should not intentionally remove:

```text
hidden text links
inline buttons
native forward metadata
Telegram media internals
```

For albums, visible links are stripped during the first send phase. After 15 seconds, the first album item's caption is edited to include the footer.

---

## 8. Movie Rule

Movie Rule is optional per pair.

### Movie Rule OFF

Every supported post is looped.

```text
Text → loop
Photo → loop
Album → loop
Video → loop
```

### Movie Rule ON

The bot reacts only when a video post appears.

But it does **not** repost the video itself.

Instead, it reposts the previous cached post unit.

Example:

```text
Channel A
Post 1 = image / album / text / movie preview
Post 2 = video
```

When Post 2 video appears:

```text
Bot uses Post 2 as trigger
Bot reposts Post 1 as content
```

Then the normal fan-out and delayed edit workflow runs.

---

## 9. Example Full Workflow

Pair channels:

```text
A, B, C, D
```

Original post appears in A.

Always Random route generated:

```text
A → C → B → D
```

### Step 1 — Send phase

The bot sends A's original post to:

```text
C
B
D
```

Visible links are removed before sending.

### Step 2 — Save message IDs

```text
C created_post_id = 101
B created_post_id = 205
D created_post_id = 77
```

### Step 3 — Wait

```text
15 seconds
```

### Step 4 — Edit phase

C post is edited with A footer:

```text
channel join - A channel link
ကြည့်ရန်လင့် - A original post link
```

B post is edited with C footer:

```text
channel join - C channel link
ကြည့်ရန်လင့် - C created post link
```

D post is edited with B footer:

```text
channel join - B channel link
ကြည့်ရန်လင့် - B created post link
```

---

## 10. Bot-created Post Protection

When the bot reposts into another channel, Telegram may send that repost back to the bot as a `channel_post` update.

The bot must not treat that repost as a new original post.

Expected behavior:

```text
Bot-created post update received
→ detect it from loop event / processed storage
→ ignore it as original source
```

This prevents infinite loops and duplicated repost chains.

---

## 11. Project Structure

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

---

## 12. Database Tables

The project uses SQLAlchemy auto-create logic on startup.

Expected tables:

```text
users
settings
pairs
pair_channels
post_units
post_items
loop_states
loop_events
processed_updates
admin_reports
```

For a larger production system, use Alembic migrations later.

---

## 13. Environment Variables

Create `.env` from `.env.example`:

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

---

## 14. Neon DB Setup

1. Create a PostgreSQL project on Neon.
2. Choose a region close to your Render region.
3. Open connection details.
4. Copy the connection string.
5. Add it to Render environment variables as `DATABASE_URL`.

Example:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require
```

The app converts the URL for asyncpg internally if the code supports it.

---

## 15. Render Deployment

### Build command

```bash
pip install -r requirements.txt
```

### Start command

```bash
python -m app.main
```

### Health check path

```text
/healthz
```

### Correct `render.yaml`

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

---

## 16. UptimeRobot Setup

1. Create a new HTTP monitor.
2. Use your Render URL.
3. Add `/healthz` at the end.

Example:

```text
https://YOUR-RENDER-APP.onrender.com/healthz
```

Expected response:

```json
{"ok": true}
```

---

## 17. Admin Commands

### `/status`

Shows users, pair count, total channels, ban status, and limits.

### `/ban user_id_or_username`

```text
/ban 123456789
/ban @username
```

### `/unban user_id_or_username`

```text
/unban 123456789
/unban @username
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
/set_ch_p_pair 123456789 6
```

### `/set_default_ch_p_pair count`

```text
/set_default_ch_p_pair 6
```

### `/user_limit count`

```text
/user_limit 100
```

Use `0` for unlimited users.

---

## 18. User Guide — English

### First setup

1. Start the bot with `/start`.
2. Add the bot as admin in every channel.
3. Give the bot **Post Messages** permission.
4. Use public channel username/link or private numeric channel ID.
5. Create a pair from the bot menu.

### Add Pair

Menu:

```text
➕ Add Pair
```

Steps:

```text
1. Choose pair number or Auto.
2. Choose repost style:
   - Always Random
   - By Order
3. Send channel links/IDs.
4. Choose Movie Rule ON/OFF.
5. Confirm.
```

---

## 19. User Guide — Myanmar

### စတင်အသုံးပြုနည်း

1. Bot ကို `/start` လုပ်ပါ။
2. အသုံးပြုမည့် channel တိုင်းတွင် bot ကို admin ထည့်ပါ။
3. Bot ကို **Post Messages** permission ပေးပါ။
4. Public channel ဆို `@username` သို့မဟုတ် `https://t.me/username` သုံးပါ။
5. Private channel ဆို bot ကို admin အရင်ထည့်ပြီး `-100...` channel ID သုံးပါ။

### Pair ထည့်နည်း

Menu:

```text
➕ Pair ထည့်မယ်
```

အဆင့်များ:

```text
1. Pair number ရွေးပါ သို့မဟုတ် Auto နှိပ်ပါ။
2. Repost style ရွေးပါ:
   - အမြဲ ကျပန်း
   - အစဉ်လိုက်
3. Channel links/IDs များပို့ပါ။
4. Movie Rule ON/OFF ရွေးပါ။
5. အတည်ပြုပါ။
```

---

## 20. Manual Test Checklist

### Startup

- [ ] `python -m app.main` starts without error.
- [ ] `/healthz` returns OK.
- [ ] Tables are created in Neon.
- [ ] `/start` shows reply keyboard.

### Pair creation

- [ ] Auto pair number works.
- [ ] Existing pair number is rejected.
- [ ] Channel count below 2 is rejected.
- [ ] Channel count above limit is rejected.
- [ ] Duplicate channels are rejected.
- [ ] Missing admin permission shows warning.
- [ ] Confirm saves pair.

### Always Random

- [ ] Post 1 route is random.
- [ ] Post 2 route changes again.
- [ ] Source channel always stays first.
- [ ] Other channels are shuffled.

### By Order

- [ ] Source channel stays first.
- [ ] Other channels follow saved order.

### Basic repost

- [ ] Text post reposts to all target channels.
- [ ] Photo post reposts to all target channels.
- [ ] Album reposts as album.
- [ ] Created message IDs are saved.
- [ ] Footer is added after 15 seconds.
- [ ] Visible links are removed.
- [ ] Bot-created posts do not start new loops.

### Footer chain

For route:

```text
A → C → B → D
```

Check:

- [ ] C footer points to A.
- [ ] B footer points to C.
- [ ] D footer points to B.

### Movie Rule

- [ ] OFF loops every supported post.
- [ ] ON ignores normal text/photo posts as trigger.
- [ ] ON reacts to video post.
- [ ] ON reposts previous cached post, not video.
- [ ] Previous album reposts as album.
- [ ] Missing previous cached post does not crash.

### Permissions

- [ ] Removing bot admin permission pauses affected pairs.
- [ ] Restoring permission reactivates pairs.
- [ ] Admin report is sent if configured.

---

## 21. Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill .env values
python -m app.main
```

For Termux, you can also run:

```bash
python -m compileall app tests
python -m app.main
```

---

## 22. GitHub Update Commands

After changing files:

```bash
git status
python -m compileall app tests
git add app/bot/services/repost_service.py app/bot/handlers/channel_posts.py app/bot/locales/en.py app/bot/locales/my.py README.md
git commit -m "update link loop workflow"
git push origin main
```

---

## 23. Production Notes

This project is suitable for one Render instance.

If traffic becomes high, consider adding:

```text
Alembic migrations
Redis lock/cache
Webhook mode
Queue worker
Better retry handling
Structured logging
```

The in-memory album collector is not safe for multiple app replicas unless album buffering is moved to Redis or database.

---

## 24. Core Rule Summary

```text
Original source channel = route[0]
Always Random = shuffle remaining channels for every new post
By Order = sort remaining channels by user-defined order
Content source = original post
Footer source = previous channel's post link
Visible links = removed before send
Footer = added after 15 seconds by editing the sent post
Bot-created posts = ignored as new original posts
```
