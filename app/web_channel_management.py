from __future__ import annotations

import logging

from aiohttp import web

from app.bot.services.pair_channel_service import (
    ChannelManagementError,
    add_channel_to_pair,
    remove_channel_from_pair,
)
from app.config import Settings
from app.db.models import User
from app.db.repository import Repository

logger = logging.getLogger(__name__)


def _error(message: str, status: int) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


async def api_add_pair_channel(request: web.Request) -> web.Response:
    repo: Repository = request["repo"]
    user: User = request["db_user"]
    try:
        pair_no = int(request.match_info["pair_no"])
        pair = await repo.get_pair_by_no(user.id, pair_no)
        if pair is None:
            return _error("Pair not found.", 404)
        try:
            data = await request.json()
        except Exception:
            return _error("Request body must be valid JSON.", 400)
        if not isinstance(data, dict):
            return _error("Request body must be a JSON object.", 400)
        raw_channel = data.get("channel")
        if not isinstance(raw_channel, str):
            return _error("Enter one channel link or channel ID.", 400)
        settings: Settings = request.app["settings"]
        await add_channel_to_pair(request.app["bot"], repo, user, pair, raw_channel, settings)
        return web.json_response({"ok": True, "message": f"Channel added to Pair {pair_no}."}, status=201)
    except ChannelManagementError as exc:
        return _error(str(exc), exc.status)
    except (TypeError, ValueError) as exc:
        return _error(str(exc), 400)
    except Exception:
        logger.exception("Mini App add-channel request failed")
        return _error("Could not add this channel. Please refresh and try again.", 500)


async def api_remove_pair_channel(request: web.Request) -> web.Response:
    repo: Repository = request["repo"]
    user: User = request["db_user"]
    try:
        pair_no = int(request.match_info["pair_no"])
        chat_id = int(request.match_info["chat_id"])
        pair = await repo.get_pair_by_no(user.id, pair_no)
        if pair is None:
            return _error("Pair not found.", 404)
        await remove_channel_from_pair(repo, user, pair, chat_id)
        return web.json_response({"ok": True, "message": f"Channel {chat_id} removed from Pair {pair_no}."})
    except ChannelManagementError as exc:
        return _error(str(exc), exc.status)
    except (TypeError, ValueError) as exc:
        return _error(str(exc), 400)
    except Exception:
        logger.exception("Mini App remove-channel request failed")
        return _error("Could not remove this channel. Please refresh and try again.", 500)
