from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), index=True)
    language: Mapped[str] = mapped_column(String(8), default='en', nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pair_limit: Mapped[int | None] = mapped_column(Integer)
    channel_per_pair_limit: Mapped[int | None] = mapped_column(Integer)

    pairs: Mapped[list['Pair']] = relationship(back_populates='user', cascade='all, delete-orphan')


class Setting(Base):
    __tablename__ = 'settings'

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Pair(Base, TimestampMixin):
    __tablename__ = 'pairs'
    __table_args__ = (UniqueConstraint('user_id', 'pair_no', name='uq_user_pair_no'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    pair_no: Mapped[int] = mapped_column(Integer, nullable=False)
    repost_style: Mapped[str] = mapped_column(String(32), default='random', nullable=False)  # random/by_order
    movie_rule: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paused_reason: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates='pairs')
    channels: Mapped[list['PairChannel']] = relationship(
        back_populates='pair', cascade='all, delete-orphan', order_by='PairChannel.order_no'
    )


class PairChannel(Base, TimestampMixin):
    __tablename__ = 'pair_channels'
    __table_args__ = (UniqueConstraint('pair_id', 'chat_id', name='uq_pair_channel_chat'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair_id: Mapped[int] = mapped_column(ForeignKey('pairs.id', ondelete='CASCADE'), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    channel_link: Mapped[str | None] = mapped_column(Text)
    invite_link: Mapped[str | None] = mapped_column(Text)
    order_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bot_admin_ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_admin_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pair: Mapped[Pair] = relationship(back_populates='channels')


class PostUnit(Base):
    __tablename__ = 'post_units'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    unit_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    first_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    media_group_id: Mapped[str | None] = mapped_column(String(255), index=True)
    post_type: Mapped[str] = mapped_column(String(32), nullable=False)  # single/album
    has_video: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    items: Mapped[list['PostItem']] = relationship(
        back_populates='post_unit', cascade='all, delete-orphan', order_by='PostItem.item_order'
    )


class PostItem(Base):
    __tablename__ = 'post_items'
    __table_args__ = (UniqueConstraint('post_unit_id', 'message_id', name='uq_post_item_msg'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_unit_id: Mapped[int] = mapped_column(ForeignKey('post_units.id', ondelete='CASCADE'), index=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)  # text/photo/video/document/audio/unsupported
    file_id: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    item_order: Mapped[int] = mapped_column(Integer, nullable=False)

    post_unit: Mapped[PostUnit] = relationship(back_populates='items')


class LoopState(Base):
    __tablename__ = 'loop_states'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loop_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    pair_id: Mapped[int] = mapped_column(ForeignKey('pairs.id', ondelete='CASCADE'), index=True, nullable=False)
    origin_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    origin_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    route_chat_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default='running', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LoopEvent(Base):
    __tablename__ = 'loop_events'
    __table_args__ = (
        UniqueConstraint('pair_id', 'to_chat_id', 'to_message_id', name='uq_loop_created_message'),
        UniqueConstraint('pair_id', 'from_chat_id', 'from_message_id', 'to_chat_id', name='uq_loop_step'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loop_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    pair_id: Mapped[int] = mapped_column(ForeignKey('pairs.id', ondelete='CASCADE'), index=True, nullable=False)
    origin_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    origin_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    from_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    from_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_bot: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default='sent', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessedUpdate(Base):
    __tablename__ = 'processed_updates'
    __table_args__ = (UniqueConstraint('pair_id', 'chat_id', 'message_id', name='uq_processed_pair_msg'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair_id: Mapped[int] = mapped_column(ForeignKey('pairs.id', ondelete='CASCADE'), index=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), default='channel_post', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminReport(Base):
    __tablename__ = 'admin_reports'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), index=True)
    pair_id: Mapped[int | None] = mapped_column(ForeignKey('pairs.id', ondelete='SET NULL'), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
