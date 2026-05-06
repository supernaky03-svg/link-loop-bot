from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.models import (
    AdminReport,
    LoopEvent,
    LoopState,
    Pair,
    PairChannel,
    PostItem,
    PostUnit,
    ProcessedUpdate,
    Setting,
    User,
)

logger = logging.getLogger(__name__)


class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- settings ----------
    async def get_setting(self, key: str) -> str | None:
        setting = await self.session.get(Setting, key)
        return setting.value if setting else None

    async def set_setting(self, key: str, value: str) -> None:
        existing = await self.session.get(Setting, key)
        if existing:
            existing.value = value
        else:
            self.session.add(Setting(key=key, value=value))
        await self.session.commit()

    async def get_int_setting(self, key: str, default: int) -> int:
        raw = await self.get_setting(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    # ---------- users ----------
    async def count_users(self) -> int:
        return int(await self.session.scalar(select(func.count(User.id))) or 0)

    async def get_user_by_tg_id(self, tg_user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.tg_user_id == tg_user_id))
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        normalized = username.lstrip('@').lower()
        result = await self.session.execute(
            select(User).where(func.lower(User.username) == normalized)
        )
        return result.scalar_one_or_none()

    async def get_or_create_user(
        self,
        tg_user_id: int,
        username: str | None,
        settings: Settings,
    ) -> tuple[User | None, bool, bool]:
        """Return (user, created, rejected_by_limit)."""
        user = await self.get_user_by_tg_id(tg_user_id)
        if user:
            new_username = username.lstrip('@') if username else None
            if user.username != new_username:
                user.username = new_username
                await self.session.commit()
            return user, False, False

        user_limit = await self.get_int_setting('user_limit', settings.user_limit)
        if user_limit > 0 and await self.count_users() >= user_limit:
            return None, False, True

        user = User(
            tg_user_id=tg_user_id,
            username=username.lstrip('@') if username else None,
            language=settings.default_language,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user, True, False

    async def list_users_with_pairs(self) -> list[User]:
        result = await self.session.execute(
            select(User).options(selectinload(User.pairs).selectinload(Pair.channels)).order_by(User.id)
        )
        return list(result.scalars().unique())

    async def set_user_banned(self, user: User, banned: bool) -> None:
        user.is_banned = banned
        await self.session.commit()

    async def set_user_pair_limit(self, tg_user_id: int, limit: int) -> bool:
        user = await self.get_user_by_tg_id(tg_user_id)
        if not user:
            return False
        user.pair_limit = limit
        await self.session.commit()
        return True

    async def set_user_channel_limit(self, tg_user_id: int, limit: int) -> bool:
        user = await self.get_user_by_tg_id(tg_user_id)
        if not user:
            return False
        user.channel_per_pair_limit = limit
        await self.session.commit()
        return True

    async def update_user_language(self, user: User, language: str) -> None:
        user.language = language
        await self.session.commit()

    # ---------- pairs ----------
    async def get_user_pairs(self, user_id: int, active_only: bool = False) -> list[Pair]:
        stmt = (
            select(Pair)
            .options(selectinload(Pair.channels), selectinload(Pair.user))
            .where(Pair.user_id == user_id)
            .order_by(Pair.pair_no)
        )
        if active_only:
            stmt = stmt.where(Pair.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().unique())

    async def get_pair_by_no(self, user_id: int, pair_no: int) -> Pair | None:
        result = await self.session.execute(
            select(Pair)
            .options(selectinload(Pair.channels), selectinload(Pair.user))
            .where(Pair.user_id == user_id, Pair.pair_no == pair_no)
        )
        return result.scalar_one_or_none()

    async def get_pair(self, pair_id: int) -> Pair | None:
        result = await self.session.execute(
            select(Pair)
            .options(selectinload(Pair.channels), selectinload(Pair.user))
            .where(Pair.id == pair_id)
        )
        return result.scalar_one_or_none()

    async def get_next_pair_no(self, user_id: int) -> int:
        numbers = await self.session.scalars(select(Pair.pair_no).where(Pair.user_id == user_id))
        used = set(numbers.all())
        n = 1
        while n in used:
            n += 1
        return n

    async def count_active_pairs(self, user_id: int) -> int:
        return int(
            await self.session.scalar(
                select(func.count(Pair.id)).where(Pair.user_id == user_id, Pair.is_active.is_(True))
            )
            or 0
        )

    async def create_pair(
        self,
        user_id: int,
        pair_no: int,
        repost_style: str,
        movie_rule: bool,
        channels: Sequence[dict],
    ) -> Pair:
        pair = Pair(
            user_id=user_id,
            pair_no=pair_no,
            repost_style=repost_style,
            movie_rule=movie_rule,
            is_active=True,
            is_paused=False,
        )
        self.session.add(pair)
        await self.session.flush()
        for idx, ch in enumerate(channels, start=1):
            self.session.add(
                PairChannel(
                    pair_id=pair.id,
                    chat_id=int(ch['chat_id']),
                    username=ch.get('username'),
                    title=ch.get('title') or str(ch['chat_id']),
                    channel_link=ch.get('channel_link'),
                    order_no=int(ch.get('order_no') or idx),
                    bot_admin_ok=True,
                    last_admin_check_at=datetime.now(timezone.utc),
                )
            )
        await self.session.commit()
        return await self.get_pair(pair.id)  # type: ignore[return-value]

    async def remove_pair(self, pair: Pair, hard_delete: bool = False) -> None:
        if hard_delete:
            await self.session.delete(pair)
        else:
            pair.is_active = False
            pair.is_paused = False
            pair.paused_reason = None
            for ch in pair.channels:
                ch.is_active = False
        await self.session.commit()

    async def update_pair_style(self, pair: Pair, style: str, order_map: dict[int, int] | None = None) -> None:
        pair.repost_style = style
        if order_map:
            for ch in pair.channels:
                if ch.chat_id in order_map:
                    ch.order_no = order_map[ch.chat_id]
        await self.session.commit()

    async def update_pair_movie_rule(self, pair: Pair, enabled: bool) -> None:
        pair.movie_rule = enabled
        await self.session.commit()

    async def active_pairs_by_chat(self, chat_id: int) -> list[Pair]:
        result = await self.session.execute(
            select(Pair)
            .join(PairChannel)
            .options(selectinload(Pair.channels), selectinload(Pair.user))
            .where(
                PairChannel.chat_id == chat_id,
                PairChannel.is_active.is_(True),
                Pair.is_active.is_(True),
            )
        )
        return list(result.scalars().unique())

    async def pause_pairs_using_channel(self, chat_id: int, reason: str) -> list[Pair]:
        pairs = await self.active_pairs_by_chat(chat_id)
        for pair in pairs:
            pair.is_paused = True
            pair.paused_reason = reason
            for channel in pair.channels:
                if channel.chat_id == chat_id:
                    channel.bot_admin_ok = False
                    channel.last_admin_check_at = datetime.now(timezone.utc)
        await self.session.commit()
        return pairs

    async def mark_channel_admin_restored(self, chat_id: int) -> list[Pair]:
        pairs = await self.active_pairs_by_chat(chat_id)
        for pair in pairs:
            for channel in pair.channels:
                if channel.chat_id == chat_id:
                    channel.bot_admin_ok = True
                    channel.last_admin_check_at = datetime.now(timezone.utc)
            if all(ch.bot_admin_ok for ch in pair.channels if ch.is_active):
                pair.is_paused = False
                pair.paused_reason = None
        await self.session.commit()
        return pairs

    # ---------- post cache ----------
    async def save_post_unit(
        self,
        chat_id: int,
        unit_key: str,
        first_message_id: int,
        last_message_id: int,
        media_group_id: str | None,
        post_type: str,
        has_video: bool,
        text: str | None,
        caption: str | None,
        items: Sequence[dict],
        cache_limit: int,
    ) -> PostUnit:
        result = await self.session.execute(select(PostUnit).where(PostUnit.unit_key == unit_key))
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        unit = PostUnit(
            chat_id=chat_id,
            unit_key=unit_key,
            first_message_id=first_message_id,
            last_message_id=last_message_id,
            media_group_id=media_group_id,
            post_type=post_type,
            has_video=has_video,
            text=text,
            caption=caption,
        )
        self.session.add(unit)
        await self.session.flush()
        for idx, item in enumerate(items, start=1):
            self.session.add(
                PostItem(
                    post_unit_id=unit.id,
                    message_id=int(item['message_id']),
                    media_type=item['media_type'],
                    file_id=item.get('file_id'),
                    caption=item.get('caption'),
                    text=item.get('text'),
                    item_order=idx,
                )
            )
        await self.session.commit()
        await self.prune_post_cache(chat_id, cache_limit)
        return await self.get_post_unit(unit.id)  # type: ignore[return-value]

    async def get_post_unit(self, post_unit_id: int) -> PostUnit | None:
        result = await self.session.execute(
            select(PostUnit).options(selectinload(PostUnit.items)).where(PostUnit.id == post_unit_id)
        )
        return result.scalar_one_or_none()

    async def get_previous_post_unit(self, chat_id: int, before_message_id: int) -> PostUnit | None:
        result = await self.session.execute(
            select(PostUnit)
            .options(selectinload(PostUnit.items))
            .where(PostUnit.chat_id == chat_id, PostUnit.last_message_id < before_message_id)
            .order_by(PostUnit.last_message_id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def prune_post_cache(self, chat_id: int, limit: int) -> None:
        if limit <= 0:
            return
        sub = (
            select(PostUnit.id)
            .where(PostUnit.chat_id == chat_id)
            .order_by(PostUnit.last_message_id.desc())
            .offset(limit)
            .subquery()
        )
        await self.session.execute(delete(PostUnit).where(PostUnit.id.in_(select(sub.c.id))))
        await self.session.commit()

    # ---------- loop protection ----------
    async def mark_processed(self, pair_id: int, chat_id: int, message_id: int) -> bool:
        self.session.add(ProcessedUpdate(pair_id=pair_id, chat_id=chat_id, message_id=message_id))
        try:
            await self.session.commit()
            return True
        except IntegrityError:
            await self.session.rollback()
            return False

    async def create_loop_state(
        self,
        loop_id: str,
        pair_id: int,
        origin_chat_id: int,
        origin_message_id: int,
        route_chat_ids: list[int],
    ) -> LoopState:
        state = LoopState(
            loop_id=loop_id,
            pair_id=pair_id,
            origin_chat_id=origin_chat_id,
            origin_message_id=origin_message_id,
            route_chat_ids=route_chat_ids,
            current_index=0,
        )
        self.session.add(state)
        await self.session.commit()
        return state

    async def get_loop_event_by_created_message(self, chat_id: int, message_id: int) -> LoopEvent | None:
        result = await self.session.execute(
            select(LoopEvent).where(
                LoopEvent.to_chat_id == chat_id,
                LoopEvent.to_message_id == message_id,
                LoopEvent.created_by_bot.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_loop_state(self, loop_id: str) -> LoopState | None:
        result = await self.session.execute(select(LoopState).where(LoopState.loop_id == loop_id))
        return result.scalar_one_or_none()

    async def save_loop_event(
        self,
        loop_id: str,
        pair_id: int,
        origin_chat_id: int,
        origin_message_id: int,
        from_chat_id: int,
        from_message_id: int,
        to_chat_id: int,
        to_message_id: int,
        status: str = 'sent',
    ) -> None:
        self.session.add(
            LoopEvent(
                loop_id=loop_id,
                pair_id=pair_id,
                origin_chat_id=origin_chat_id,
                origin_message_id=origin_message_id,
                from_chat_id=from_chat_id,
                from_message_id=from_message_id,
                to_chat_id=to_chat_id,
                to_message_id=to_message_id,
                created_by_bot=True,
                status=status,
            )
        )
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            logger.info('duplicate loop event ignored', extra={'loop_id': loop_id, 'pair_id': pair_id})

    async def update_loop_index(self, loop_id: str, current_index: int, status: str = 'running') -> None:
        await self.session.execute(
            update(LoopState)
            .where(LoopState.loop_id == loop_id)
            .values(current_index=current_index, status=status)
        )
        await self.session.commit()

    # ---------- reports ----------
    async def create_admin_report(
        self,
        user_id: int | None,
        pair_id: int | None,
        chat_id: int,
        report_type: str,
        message: str,
    ) -> AdminReport:
        report = AdminReport(
            user_id=user_id,
            pair_id=pair_id,
            chat_id=chat_id,
            report_type=report_type,
            message=message,
        )
        self.session.add(report)
        await self.session.commit()
        return report
