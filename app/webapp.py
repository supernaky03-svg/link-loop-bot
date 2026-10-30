from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web
from sqlalchemy.exc import IntegrityError

from app.bot.services.channel_service import parse_channel_list, resolve_and_check_channel
from app.bot.services.pair_service import user_limits
from app.config import Settings
from app.db.models import Pair, Setting, User
from app.db.repository import Repository
from app.db.session import AsyncSessionLocal
from app.webapp_auth import InitDataError, validate_telegram_init_data

logger = logging.getLogger(__name__)
WEB_DIR = Path(__file__).resolve().parent / "web"


def json_error(message: str, status: int) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


@web.middleware
async def telegram_auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/api/"):
        return await handler(request)
    settings: Settings = request.app["settings"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    auth_header = request.headers.get("Authorization", "")
    if not init_data and auth_header.startswith("tma "):
        init_data = auth_header[4:].strip()
    try:
        auth = validate_telegram_init_data(init_data, settings.bot_token)
    except InitDataError as exc:
        return json_error(str(exc), 401)

    tg_user = auth["user"]
    try:
        async with AsyncSessionLocal() as session:
            repo = Repository(session)
            user, _created, rejected = await repo.get_or_create_user(
                tg_user_id=int(tg_user["id"]), username=tg_user.get("username"), settings=settings
            )
            if rejected or user is None:
                return json_error("The bot user limit has been reached.", 403)
            is_admin = int(tg_user["id"]) in settings.admin_ids
            if user.is_banned and not is_admin:
                return json_error("This account is blocked. Contact the administrator.", 403)
            request["session"] = session
            request["repo"] = repo
            request["db_user"] = user
            request["telegram_user"] = tg_user
            request["is_admin"] = is_admin
            return await handler(request)
    except web.HTTPException:
        raise
    except Exception:
        logger.exception("Mini App API request failed", extra={"path": request.path})
        return json_error("Internal server error. Please try again.", 500)


async def read_json(request: web.Request) -> dict:
    try:
        data = await request.json()
    except (json.JSONDecodeError, web.HTTPBadRequest):
        raise ValueError("Request body must be valid JSON") from None
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")
    return data


def channel_payload(channel) -> dict:
    return {
        "chat_id": channel.chat_id,
        "title": channel.title,
        "username": channel.username,
        "channel_link": channel.channel_link,
        "invite_link": channel.invite_link,
        "order_no": channel.order_no,
        "is_active": channel.is_active,
        "bot_admin_ok": channel.bot_admin_ok,
    }


def pair_payload(pair: Pair) -> dict:
    return {
        "id": pair.id,
        "pair_no": pair.pair_no,
        "repost_style": pair.repost_style,
        "movie_rule": pair.movie_rule,
        "is_active": pair.is_active,
        "is_paused": pair.is_paused,
        "paused_reason": pair.paused_reason,
        "channels": [channel_payload(ch) for ch in sorted(pair.channels, key=lambda item: item.order_no)],
    }


async def mini_app_index(_request: web.Request) -> web.Response:
    return web.FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


async def health_ok(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def api_bootstrap(request: web.Request) -> web.Response:
    repo: Repository = request["repo"]
    user: User = request["db_user"]
    settings: Settings = request.app["settings"]
    pair_limit, channel_limit = await user_limits(repo, user, settings)
    pairs = await repo.get_user_pairs(user.id, active_only=True)
    return web.json_response({
        "ok": True,
        "profile": {
            "telegram_id": user.tg_user_id,
            "username": user.username,
            "language": user.language,
            "is_admin": request["is_admin"],
            "pair_limit": pair_limit,
            "channel_per_pair_limit": channel_limit,
        },
        "pairs": [pair_payload(pair) for pair in pairs],
        "contact_admin": settings.admin_contact,
    })


async def validated_channels(request: web.Request, data: dict, user: User) -> tuple[list[dict], str]:
    repo: Repository = request["repo"]
    settings: Settings = request.app["settings"]
    style = str(data.get("repost_style") or "random")
    if style not in {"random", "by_order"}:
        raise ValueError("Invalid repost style")
    raw = str(data.get("channels") or "").strip()
    if not raw:
        raise ValueError("Enter at least two channel links or IDs separated by commas.")
    _pair_limit, channel_limit = await user_limits(repo, user, settings)
    inputs = parse_channel_list(raw, by_order=style == "by_order")
    if len(inputs) < 2 or len(inputs) > channel_limit:
        raise ValueError(f"Channel count must be between 2 and {channel_limit}.")
    invalid = [item.raw for item in inputs if item.error]
    if invalid:
        raise ValueError("Invalid channel input: " + ", ".join(invalid))
    missing = [item.raw for item in inputs if item.missing]
    if missing:
        raise ValueError(
            "Private channels require both the numeric -100… channel ID and invite link. "
            "Example: https://t.me/+invite(-1001234567890). Unmatched: " + ", ".join(missing)
        )

    checks = [await resolve_and_check_channel(request.app["bot"], item, item.order_no) for item in inputs]
    ids = [item.chat_id for item in checks if item.chat_id is not None]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate channels are not allowed in one pair.")
    failures = [item for item in checks if not item.ok]
    if failures:
        detail = ", ".join(f"{item.title or item.input_value} ({item.error or 'permission missing'})" for item in failures)
        raise ValueError("Bot admin/Post Messages permission is missing: " + detail)

    channels = [{
        "chat_id": int(item.chat_id),
        "title": item.title or str(item.chat_id),
        "username": item.username,
        "channel_link": item.channel_link,
        "invite_link": item.invite_link,
        "order_no": int(item.order_no or index),
    } for index, item in enumerate(checks, start=1)]
    return channels, style


async def api_create_pair(request: web.Request) -> web.Response:
    repo: Repository = request["repo"]
    user: User = request["db_user"]
    settings: Settings = request.app["settings"]
    try:
        data = await read_json(request)
        pair_limit, _ = await user_limits(repo, user, settings)
        if await repo.count_active_pairs(user.id) >= pair_limit:
            return json_error(f"Pair limit reached ({pair_limit}).", 409)
        raw_no = data.get("pair_no")
        if isinstance(raw_no, bool):
            raise ValueError("Pair number must be a positive integer or Auto.")
        pair_no = await repo.get_next_pair_no(user.id) if raw_no in (None, "", "auto", "Auto") else int(raw_no)
        if pair_no <= 0:
            raise ValueError("Pair number must be positive.")
        existing = await repo.get_pair_by_no(user.id, pair_no, active_only=False)
        if existing and existing.is_active:
            return json_error(f"Pair {pair_no} already exists.", 409)
        channels, style = await validated_channels(request, data, user)
        movie_rule = data.get("movie_rule", False)
        if not isinstance(movie_rule, bool):
            raise ValueError("Movie Rule must be true or false.")
        try:
            pair = await repo.create_pair(user.id, pair_no, style, movie_rule, channels)
        except IntegrityError:
            await request["session"].rollback()
            return json_error("Pair number or channel assignment conflicts with another update. Refresh and retry.", 409)
        return web.json_response({"ok": True, "pair": pair_payload(pair)}, status=201)
    except (TypeError, ValueError) as exc:
        return json_error(str(exc), 400)


async def api_update_pair(request: web.Request) -> web.Response:
    repo: Repository = request["repo"]
    user: User = request["db_user"]
    try:
        pair_no = int(request.match_info["pair_no"])
        pair = await repo.get_pair_by_no(user.id, pair_no)
        if not pair:
            return json_error("Pair not found.", 404)
        data = await read_json(request)
        if not data:
            raise ValueError("No settings were supplied.")
        if "repost_style" in data:
            style = str(data["repost_style"])
            if style not in {"random", "by_order"}:
                raise ValueError("Invalid repost style.")
            order_map = None
            if style == "by_order" and "order" in data:
                values = data["order"]
                if not isinstance(values, list) or any(isinstance(v, bool) for v in values):
                    raise ValueError("Channel order must be a list of channel IDs.")
                ordered = [int(v) for v in values]
                current = [ch.chat_id for ch in pair.channels if ch.is_active]
                if len(ordered) != len(current) or set(ordered) != set(current):
                    raise ValueError("Order must contain every active channel exactly once.")
                order_map = {chat_id: idx for idx, chat_id in enumerate(ordered, 1)}
            pair.repost_style = style
            if order_map:
                for ch in pair.channels:
                    if ch.chat_id in order_map:
                        ch.order_no = order_map[ch.chat_id]
        if "movie_rule" in data:
            if not isinstance(data["movie_rule"], bool):
                raise ValueError("Movie Rule must be true or false.")
            pair.movie_rule = data["movie_rule"]
        await request["session"].commit()
        refreshed = await repo.get_pair_by_no(user.id, pair_no)
        return web.json_response({"ok": True, "pair": pair_payload(refreshed)})
    except (TypeError, ValueError) as exc:
        return json_error(str(exc), 400)


async def api_delete_pair(request: web.Request) -> web.Response:
    repo: Repository = request["repo"]
    user: User = request["db_user"]
    pair = await repo.get_pair_by_no(user.id, int(request.match_info["pair_no"]))
    if not pair:
        return json_error("Pair not found.", 404)
    await repo.remove_pair(pair, hard_delete=False)
    return web.json_response({"ok": True, "message": f"Pair {pair.pair_no} removed."})


async def api_recheck_pair(request: web.Request) -> web.Response:
    repo: Repository = request["repo"]
    user: User = request["db_user"]
    pair = await repo.get_pair_by_no(user.id, int(request.match_info["pair_no"]))
    if not pair:
        return json_error("Pair not found.", 404)
    failures = []
    for channel in pair.channels:
        checked = await resolve_and_check_channel(request.app["bot"], str(channel.chat_id), channel.order_no)
        channel.bot_admin_ok = bool(checked.ok)
        channel.last_admin_check_at = datetime.now(timezone.utc)
        if not checked.ok:
            failures.append(channel.title)
    pair.is_paused = bool(failures)
    pair.paused_reason = "bot_admin_missing" if failures else None
    await request["session"].commit()
    refreshed = await repo.get_pair_by_no(user.id, pair.pair_no)
    message = "Permission is still missing: " + ", ".join(failures) if failures else "All channel permissions are OK. Pair resumed."
    return web.json_response({"ok": True, "pair": pair_payload(refreshed), "message": message})


async def api_update_profile(request: web.Request) -> web.Response:
    try:
        data = await read_json(request)
        language = str(data.get("language") or "")
        if language not in {"en", "my"}:
            raise ValueError("Language must be en or my.")
        await request["repo"].update_user_language(request["db_user"], language)
        return web.json_response({"ok": True, "language": language})
    except ValueError as exc:
        return json_error(str(exc), 400)


async def require_admin(request: web.Request) -> web.Response | None:
    return None if request["is_admin"] else json_error("Admin only.", 403)


async def api_admin_dashboard(request: web.Request) -> web.Response:
    denied = await require_admin(request)
    if denied:
        return denied
    repo: Repository = request["repo"]
    settings: Settings = request.app["settings"]
    users = await repo.list_users_with_pairs()
    global_pair = await repo.get_int_setting("default_pair_limit", settings.default_pair_limit)
    global_channels = await repo.get_int_setting("default_channel_per_pair_limit", settings.default_channel_per_pair_limit)
    user_limit = await repo.get_int_setting("user_limit", settings.user_limit)
    rows, pair_total, channel_total = [], 0, 0
    for item in users:
        active = [pair for pair in item.pairs if pair.is_active]
        channels = sum(sum(1 for ch in pair.channels if ch.is_active) for pair in active)
        pair_total += len(active)
        channel_total += channels
        rows.append({
            "telegram_id": item.tg_user_id,
            "username": item.username,
            "is_banned": item.is_banned,
            "pair_limit": item.pair_limit,
            "channel_per_pair_limit": item.channel_per_pair_limit,
            "active_pairs": len(active),
            "channels": channels,
        })
    return web.json_response({
        "ok": True,
        "stats": {"users": len(users), "active_pairs": pair_total, "channels": channel_total},
        "settings": {"default_pair_limit": global_pair, "default_channel_per_pair_limit": global_channels, "user_limit": user_limit},
        "users": rows,
    })


async def api_admin_update_user(request: web.Request) -> web.Response:
    denied = await require_admin(request)
    if denied:
        return denied
    try:
        tg_id = int(request.match_info["tg_user_id"])
        data = await read_json(request)
        if tg_id in request.app["settings"].admin_ids and data.get("is_banned") is True:
            return json_error("You cannot ban an administrator account.", 400)
        target = await request["repo"].get_user_by_tg_id(tg_id)
        if not target:
            return json_error("User not found.", 404)
        changed = False
        if "is_banned" in data:
            if not isinstance(data["is_banned"], bool):
                raise ValueError("is_banned must be true or false.")
            target.is_banned = data["is_banned"]
            changed = True
        for key in ("pair_limit", "channel_per_pair_limit"):
            if key in data:
                value = data[key]
                if value is not None:
                    if isinstance(value, bool):
                        raise ValueError(f"{key} must be a non-negative integer or null.")
                    value = int(value)
                    if value < 0:
                        raise ValueError(f"{key} cannot be negative.")
                setattr(target, key, value)
                changed = True
        if not changed:
            raise ValueError("No supported user setting was supplied.")
        await request["session"].commit()
        return web.json_response({"ok": True})
    except (TypeError, ValueError) as exc:
        return json_error(str(exc), 400)


async def api_admin_update_settings(request: web.Request) -> web.Response:
    denied = await require_admin(request)
    if denied:
        return denied
    allowed = {"default_pair_limit", "default_channel_per_pair_limit", "user_limit"}
    try:
        data = await read_json(request)
        if not data or set(data) - allowed:
            raise ValueError("Unsupported or missing global settings.")
        parsed = {}
        for key, value in data.items():
            if isinstance(value, bool):
                raise ValueError(f"{key} must be an integer.")
            number = int(value)
            if number < 0:
                raise ValueError(f"{key} cannot be negative.")
            parsed[key] = str(number)
        # One DB transaction: avoid partial updates if one setting fails.
        for key, value in parsed.items():
            setting = await request["session"].get(Setting, key)
            if setting:
                setting.value = value
            else:
                request["session"].add(Setting(key=key, value=value))
        await request["session"].commit()
        return web.json_response({"ok": True})
    except (TypeError, ValueError) as exc:
        await request["session"].rollback()
        return json_error(str(exc), 400)


async def api_admin_status_report(request: web.Request) -> web.Response:
    denied = await require_admin(request)
    if denied:
        return denied
    repo: Repository = request["repo"]
    settings: Settings = request.app["settings"]
    users = await repo.list_users_with_pairs()
    default_pair = await repo.get_int_setting("default_pair_limit", settings.default_pair_limit)
    default_channels = await repo.get_int_setting("default_channel_per_pair_limit", settings.default_channel_per_pair_limit)
    blocks = [f"Total Bot Users: {len(users)}"]
    for index, item in enumerate(users, 1):
        active = [pair for pair in item.pairs if pair.is_active]
        channel_count = sum(sum(1 for ch in pair.channels if ch.is_active) for pair in active)
        blocks.append(
            f"────────── User {index} ──────────\n"
            f"Username: {'@' + item.username if item.username else '-'}\n"
            f"User ID: {item.tg_user_id}\nPair Count: {len(active)}\nTotal Channels: {channel_count}\n"
            f"Banned: {'Yes' if item.is_banned else 'No'}\n"
            f"Pair Limit: {item.pair_limit or default_pair}\n"
            f"Channel Per Pair Limit: {item.channel_per_pair_limit or default_channels}"
        )
    text = "\n\n".join(blocks) if users else "No users found."
    chunks, current = [], ""
    for block in text.split("\n\n"):
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) > 3900 and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    try:
        for chunk in chunks:
            await request.app["bot"].send_message(settings.report_group_id, chunk)
    except Exception:
        logger.exception("Mini App status report delivery failed")
        return json_error("Could not send status report to the configured report group.", 502)
    return web.json_response({"ok": True, "message": "Status report sent to the report group."})


def create_web_app(settings: Settings, bot) -> web.Application:
    app = web.Application(middlewares=[telegram_auth_middleware], client_max_size=64 * 1024)
    app["settings"] = settings
    app["bot"] = bot
    app.router.add_get(settings.health_path, health_ok)
    app.router.add_get("/", mini_app_index)
    app.router.add_get("/app", mini_app_index)
    app.router.add_get("/api/bootstrap", api_bootstrap)
    app.router.add_post("/api/pairs", api_create_pair)
    app.router.add_put(r"/api/pairs/{pair_no:\d+}", api_update_pair)
    app.router.add_delete(r"/api/pairs/{pair_no:\d+}", api_delete_pair)
    app.router.add_post(r"/api/pairs/{pair_no:\d+}/recheck", api_recheck_pair)
    app.router.add_put("/api/profile", api_update_profile)
    app.router.add_get("/api/admin", api_admin_dashboard)
    app.router.add_patch(r"/api/admin/users/{tg_user_id:\d+}", api_admin_update_user)
    app.router.add_patch("/api/admin/settings", api_admin_update_settings)
    app.router.add_post("/api/admin/status-report", api_admin_status_report)
    return app
