from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.services.language_service import t
from app.config import Settings, get_settings
from app.db.models import User
from app.db.repository import Repository

logger = logging.getLogger(__name__)
router = Router(name='admin')


TELEGRAM_SAFE_TEXT_LIMIT = 3900


def _is_admin(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.admin_ids)


def _args(message: Message) -> list[str]:
    text = message.text or ''
    return text.split()[1:]


async def _resolve_user(repo: Repository, value: str) -> User | None:
    if value.lstrip('-').isdigit():
        return await repo.get_user_by_tg_id(int(value))
    return await repo.get_user_by_username(value)


def _split_text(text: str, limit: int = TELEGRAM_SAFE_TEXT_LIMIT) -> list[str]:
    """Split long Telegram messages on block/newline boundaries where possible."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ''
    for block in text.split('\n\n'):
        addition = block if not current else f'\n\n{block}'
        if len(current) + len(addition) <= limit:
            current += addition
            continue
        if current:
            chunks.append(current)
            current = ''
        if len(block) <= limit:
            current = block
            continue
        for start in range(0, len(block), limit):
            chunks.append(block[start : start + limit])
    if current:
        chunks.append(current)
    return chunks


async def _build_status_text(repo: Repository, settings: Settings, language: str) -> str:
    users = await repo.list_users_with_pairs()
    if not users:
        return t(language, 'status_empty')

    default_pair_limit = await repo.get_int_setting('default_pair_limit', settings.default_pair_limit)
    default_ch_limit = await repo.get_int_setting(
        'default_channel_per_pair_limit', settings.default_channel_per_pair_limit
    )
    blocks = [f'Total Bot Users: {len(users)}']
    for idx, user in enumerate(users, start=1):
        pair_count = len([p for p in user.pairs if p.is_active])
        total_channels = sum(len([c for c in p.channels if c.is_active]) for p in user.pairs if p.is_active)
        username = f'@{user.username}' if user.username else '-'
        blocks.append(
            f'────────── User {idx} ──────────\n'
            f'Username: {username}\n'
            f'User ID: {user.tg_user_id}\n'
            f'Pair Count: {pair_count}\n'
            f'Total Channels: {total_channels}\n'
            f'Banned: {"Yes" if user.is_banned else "No"}\n'
            f'Pair Limit: {user.pair_limit or default_pair_limit}\n'
            f'Channel Per Pair Limit: {user.channel_per_pair_limit or default_ch_limit}'
        )
    return '\n\n'.join(blocks)


@router.message(Command('status'))
async def status(message: Message, repo: Repository, language: str) -> None:
    settings = get_settings()
    if not _is_admin(message, settings):
        await message.answer(t(language, 'admin_only'))
        return

    args = _args(message)
    target = args[0].lower() if args else 'here'
    if target not in {'here', 'group'}:
        await message.answer(t(language, 'usage_error'))
        return

    text = await _build_status_text(repo, settings, language)
    chunks = _split_text(text)

    if target == 'group':
        try:
            for chunk in chunks:
                await message.bot.send_message(settings.report_group_id, chunk)
        except Exception:
            logger.exception(
                'failed to send status report to report group',
                extra={'report_group_id': settings.report_group_id, 'admin_id': message.from_user.id if message.from_user else None},
            )
            await message.answer(t(language, 'status_report_failed'))
            return
        await message.answer(t(language, 'status_report_sent'))
        return

    for chunk in chunks:
        await message.answer(chunk)


@router.message(Command('ban'))
async def ban(message: Message, repo: Repository, language: str) -> None:
    settings = get_settings()
    if not _is_admin(message, settings):
        await message.answer(t(language, 'admin_only'))
        return
    args = _args(message)
    if len(args) != 1:
        await message.answer(t(language, 'usage_error'))
        return
    user = await _resolve_user(repo, args[0])
    if not user:
        await message.answer(t(language, 'user_not_found'))
        return
    await repo.set_user_banned(user, True)
    await message.answer(t(language, 'banned_ok'))


@router.message(Command('unban'))
async def unban(message: Message, repo: Repository, language: str) -> None:
    settings = get_settings()
    if not _is_admin(message, settings):
        await message.answer(t(language, 'admin_only'))
        return
    args = _args(message)
    if len(args) != 1:
        await message.answer(t(language, 'usage_error'))
        return
    user = await _resolve_user(repo, args[0])
    if not user:
        await message.answer(t(language, 'user_not_found'))
        return
    await repo.set_user_banned(user, False)
    await message.answer(t(language, 'unbanned_ok'))


@router.message(Command('set_pair_limit'))
async def set_pair_limit(message: Message, repo: Repository, language: str) -> None:
    settings = get_settings()
    if not _is_admin(message, settings):
        await message.answer(t(language, 'admin_only'))
        return
    args = _args(message)
    if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit():
        await message.answer(t(language, 'usage_error'))
        return
    ok = await repo.set_user_pair_limit(int(args[0]), int(args[1]))
    await message.answer(t(language, 'limit_saved') if ok else t(language, 'user_not_found'))


@router.message(Command('set_default_pair_limit'))
async def set_default_pair_limit(message: Message, repo: Repository, language: str) -> None:
    settings = get_settings()
    if not _is_admin(message, settings):
        await message.answer(t(language, 'admin_only'))
        return
    args = _args(message)
    if len(args) != 1 or not args[0].isdigit():
        await message.answer(t(language, 'usage_error'))
        return
    await repo.set_setting('default_pair_limit', args[0])
    await message.answer(t(language, 'limit_saved'))


@router.message(Command('set_ch_p_pair'))
async def set_ch_p_pair(message: Message, repo: Repository, language: str) -> None:
    settings = get_settings()
    if not _is_admin(message, settings):
        await message.answer(t(language, 'admin_only'))
        return
    args = _args(message)
    if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit():
        await message.answer(t(language, 'usage_error'))
        return
    ok = await repo.set_user_channel_limit(int(args[0]), int(args[1]))
    await message.answer(t(language, 'limit_saved') if ok else t(language, 'user_not_found'))


@router.message(Command('set_default_ch_p_pair'))
async def set_default_ch_p_pair(message: Message, repo: Repository, language: str) -> None:
    settings = get_settings()
    if not _is_admin(message, settings):
        await message.answer(t(language, 'admin_only'))
        return
    args = _args(message)
    if len(args) != 1 or not args[0].isdigit():
        await message.answer(t(language, 'usage_error'))
        return
    await repo.set_setting('default_channel_per_pair_limit', args[0])
    await message.answer(t(language, 'limit_saved'))


@router.message(Command('user_limit'))
async def user_limit(message: Message, repo: Repository, language: str) -> None:
    settings = get_settings()
    if not _is_admin(message, settings):
        await message.answer(t(language, 'admin_only'))
        return
    args = _args(message)
    if len(args) != 1 or not args[0].isdigit():
        await message.answer(t(language, 'usage_error'))
        return
    await repo.set_setting('user_limit', args[0])
    await message.answer(t(language, 'limit_saved'))
