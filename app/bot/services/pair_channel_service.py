from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.bot.services.pair_service import user_limits
from app.config import Settings
from app.db.models import Pair, PairChannel, User
from app.db.repository import Repository


class ChannelManagementError(ValueError):
    """A safe, user-displayable error raised by pair channel operations."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


async def _parse_single_channel(raw: str) -> Any:
    # Lazy import keeps the persistence/domain tests independent from aiogram.
    from app.bot.services.channel_service import parse_channel_list

    items = parse_channel_list(raw, by_order=False)
    if len(items) != 1:
        raise ChannelManagementError(
            "Send exactly one channel per request. Public: @username or https://t.me/name. "
            "Private: invite link plus numeric -100… channel ID."
        )
    item = items[0]
    if item.error:
        raise ChannelManagementError("Invalid channel input. Use a public channel link or a private invite-link/ID pair.")
    if item.missing:
        raise ChannelManagementError(
            "Private channels need both the invite link and numeric -100… ID, "
            "for example https://t.me/+invite(-1001234567890)."
        )
    return item


async def _resolve_channel(bot: Any, parsed: Any) -> Any:
    from app.bot.services.channel_service import resolve_and_check_channel

    return await resolve_and_check_channel(bot, parsed, parsed.order_no)


def _active_channels(pair: Pair) -> list[PairChannel]:
    return sorted((ch for ch in pair.channels if ch.is_active), key=lambda ch: (ch.order_no, ch.id or 0))


def _reindex_active_channels(pair: Pair) -> None:
    for order_no, channel in enumerate(_active_channels(pair), start=1):
        channel.order_no = order_no


async def _commit_and_refresh(repo: Repository, user: User, pair: Pair) -> Pair:
    try:
        await repo.session.commit()
    except IntegrityError as exc:
        await repo.session.rollback()
        raise ChannelManagementError(
            "This channel was changed at the same time in another request. Refresh the pair and try again.",
            409,
        ) from exc
    refreshed = await repo.get_pair_by_no(user.id, pair.pair_no)
    if refreshed is None:
        raise ChannelManagementError("Pair not found after saving. Refresh and try again.", 404)
    return refreshed


async def add_channel_to_pair(
    bot: Any,
    repo: Repository,
    user: User,
    pair: Pair,
    raw_channel: str,
    settings: Settings,
) -> Pair:
    """Validate and add/reactivate exactly one channel in a user's pair.

    Bot and Mini App both call this function so ownership, Telegram permission,
    duplicate and per-user channel-limit rules stay identical.
    """
    raw = (raw_channel or "").strip()
    if not raw or len(raw) > 2048:
        raise ChannelManagementError("Enter one channel link or channel ID.")
    parsed = await _parse_single_channel(raw)
    checked = await _resolve_channel(bot, parsed)
    if not checked.ok or checked.chat_id is None:
        if checked.error == "missing_admin":
            raise ChannelManagementError(
                f"Bot admin permission is missing for {checked.title or raw}. "
                "Add the bot as channel admin with Post Messages permission, then retry.",
                403,
            )
        raise ChannelManagementError(
            f"Could not verify channel '{raw}'. Check the channel link/ID and make sure the bot can access it.",
            400,
        )

    existing = next((ch for ch in pair.channels if ch.chat_id == int(checked.chat_id)), None)
    if existing is not None and existing.is_active:
        raise ChannelManagementError("This channel is already active in this pair.", 409)

    _pair_limit, channel_limit = await user_limits(repo, user, settings)
    active = _active_channels(pair)
    if len(active) >= channel_limit:
        raise ChannelManagementError(f"Channel limit reached ({channel_limit}) for this pair.", 409)

    next_order = len(active) + 1
    now = datetime.now(timezone.utc)
    if existing is not None:
        # Reuse the soft-removed row; the DB unique constraint is pair_id/chat_id.
        existing.title = checked.title or str(checked.chat_id)
        existing.username = checked.username
        existing.channel_link = checked.channel_link
        existing.invite_link = checked.invite_link
        existing.order_no = next_order
        existing.is_active = True
        existing.bot_admin_ok = True
        existing.last_admin_check_at = now
    else:
        channel = PairChannel(
            pair_id=pair.id,
            chat_id=int(checked.chat_id),
            username=checked.username,
            title=checked.title or str(checked.chat_id),
            channel_link=checked.channel_link,
            invite_link=checked.invite_link,
            order_no=next_order,
            is_active=True,
            bot_admin_ok=True,
            last_admin_check_at=now,
        )
        pair.channels.append(channel)

    active_after = _active_channels(pair)
    # Only the specific automatic pause may be cleared here. Permission or any
    # other pause reason must never be silently overridden.
    if (
        len(active_after) >= 2
        and pair.is_paused
        and pair.paused_reason in {"insufficient_channels", "bot_admin_missing"}
        and all(ch.bot_admin_ok for ch in active_after)
    ):
        pair.is_paused = False
        pair.paused_reason = None
    _reindex_active_channels(pair)
    return await _commit_and_refresh(repo, user, pair)


async def remove_channel_from_pair(
    repo: Repository,
    user: User,
    pair: Pair,
    chat_id: int,
) -> Pair:
    """Soft-remove one channel while preserving repost/history references."""
    target = next(
        (ch for ch in pair.channels if ch.chat_id == int(chat_id) and ch.is_active),
        None,
    )
    if target is None:
        raise ChannelManagementError("That channel is not active in this pair.", 404)

    target.is_active = False
    active_after = _active_channels(pair)
    _reindex_active_channels(pair)

    if len(active_after) < 2:
        # Keep the pair record and channel metadata so the user can add a
        # replacement later. Do not overwrite an unrelated/manual pause reason.
        # The automatic reason can be cleared after a valid replacement is added.
        if not pair.is_paused or pair.paused_reason in {"insufficient_channels", "bot_admin_missing"}:
            pair.is_paused = True
            pair.paused_reason = "insufficient_channels"
    elif pair.is_paused and pair.paused_reason in {"insufficient_channels", "bot_admin_missing"}:
        # Removing a permission-broken channel may restore a healthy route.
        if all(ch.bot_admin_ok for ch in active_after):
            pair.is_paused = False
            pair.paused_reason = None

    return await _commit_and_refresh(repo, user, pair)
