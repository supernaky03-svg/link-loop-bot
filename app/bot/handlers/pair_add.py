from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.inline import (
    confirm_keyboard,
    flow_nav_keyboard,
    on_off_keyboard,
    pair_no_keyboard,
    recheck_keyboard,
    style_keyboard,
)
from app.bot.keyboards.reply import main_menu
from app.bot.services.channel_service import ChannelCheckResult, parse_channel_list, resolve_and_check_channel
from app.bot.services.flow_message import update_flow_message
from app.bot.services.language_service import b, t
from app.bot.services.pair_service import user_limits
from app.bot.states.pair_states import AddPairStates
from app.config import get_settings
from app.db.models import User
from app.db.repository import Repository

logger = logging.getLogger(__name__)
router = Router(name='pair_add')


def _add_buttons() -> set[str]:
    return {b('en', 'add_pair'), b('my', 'add_pair')}


async def _show_pair_no(message_or_callback, state: FSMContext, language: str) -> None:
    chat_id = message_or_callback.message.chat.id if isinstance(message_or_callback, CallbackQuery) else message_or_callback.chat.id
    bot = message_or_callback.bot
    await state.set_state(AddPairStates.waiting_pair_no)
    await update_flow_message(bot, state, chat_id, t(language, 'add_pair_step_pair_no'), pair_no_keyboard(language))


async def _show_style(message_or_callback, state: FSMContext, language: str) -> None:
    chat_id = message_or_callback.message.chat.id if isinstance(message_or_callback, CallbackQuery) else message_or_callback.chat.id
    bot = message_or_callback.bot
    await state.set_state(AddPairStates.waiting_style)
    await update_flow_message(bot, state, chat_id, t(language, 'add_pair_step_style'), style_keyboard(language, 'add'))


async def _show_channels(message_or_callback, state: FSMContext, language: str) -> None:
    data = await state.get_data()
    style = data.get('repost_style', 'random')
    key = 'add_pair_step_channels_order' if style == 'by_order' else 'add_pair_step_channels_random'
    chat_id = message_or_callback.message.chat.id if isinstance(message_or_callback, CallbackQuery) else message_or_callback.chat.id
    bot = message_or_callback.bot
    await state.set_state(AddPairStates.waiting_channels)
    await update_flow_message(bot, state, chat_id, t(language, key), flow_nav_keyboard(language))


async def _show_movie(message_or_callback, state: FSMContext, language: str) -> None:
    chat_id = message_or_callback.message.chat.id if isinstance(message_or_callback, CallbackQuery) else message_or_callback.chat.id
    bot = message_or_callback.bot
    await state.set_state(AddPairStates.waiting_movie_rule)
    await update_flow_message(bot, state, chat_id, t(language, 'add_pair_step_movie'), on_off_keyboard(language, 'add:movie'))


async def _show_confirm(message_or_callback, state: FSMContext, language: str) -> None:
    data = await state.get_data()
    channels = data.get('channels', [])
    channel_lines = '\n'.join(
        f"{ch['order_no']}. {ch['title']} ({ch['chat_id']})" for ch in sorted(channels, key=lambda x: x['order_no'])
    )
    text = t(
        language,
        'add_pair_confirm',
        pair_no=data['pair_no'],
        style=t(language, data['repost_style']),
        movie_rule=t(language, 'on' if data.get('movie_rule') else 'off'),
        channels=channel_lines,
    )
    chat_id = message_or_callback.message.chat.id if isinstance(message_or_callback, CallbackQuery) else message_or_callback.chat.id
    bot = message_or_callback.bot
    await state.set_state(AddPairStates.confirmation)
    await update_flow_message(bot, state, chat_id, text, confirm_keyboard(language, 'add'))


async def _check_pair_limit(repo: Repository, db_user: User) -> tuple[bool, int]:
    settings = get_settings()
    pair_limit, _ = await user_limits(repo, db_user, settings)
    current = await repo.count_active_pairs(db_user.id)
    return current < pair_limit, pair_limit


async def _validate_and_resolve_channels(
    bot,
    repo: Repository,
    db_user: User,
    language: str,
    raw: str,
    by_order: bool,
) -> tuple[bool, str | None, list[dict]]:
    settings = get_settings()
    _, channel_limit = await user_limits(repo, db_user, settings)
    parsed = parse_channel_list(raw, by_order)
    if len(parsed) < 2 or len(parsed) > channel_limit:
        return False, t(language, 'channel_count_error', limit=channel_limit), []

    checks: list[ChannelCheckResult] = []
    for order_no, value in parsed:
        checks.append(await resolve_and_check_channel(bot, value, order_no))

    resolved = [c for c in checks if c.chat_id is not None]
    ids = [c.chat_id for c in resolved]
    if len(ids) != len(set(ids)):
        return False, t(language, 'duplicate_channels'), []

    errors = [c for c in checks if not c.ok]
    if errors:
        lines = [t(language, 'missing_admin_title')]
        for idx, err in enumerate(errors, start=1):
            if err.chat_id:
                lines.append(f'{idx}. {err.title or err.input_value} ({err.chat_id})')
            else:
                lines.append(f'{idx}. {err.input_value}')
        lines.append('')
        lines.append(t(language, 'missing_admin_footer'))
        return False, '\n'.join(lines), []

    channels = [
        {
            'chat_id': int(c.chat_id),
            'title': c.title,
            'username': c.username,
            'channel_link': c.channel_link,
            'order_no': int(c.order_no or idx),
        }
        for idx, c in enumerate(checks, start=1)
    ]
    return True, None, channels


@router.message(F.text.in_(_add_buttons()))
async def begin_add_pair(message: Message, state: FSMContext, language: str) -> None:
    await state.clear()
    await _show_pair_no(message, state, language)


@router.callback_query(AddPairStates.waiting_pair_no, F.data == 'add:auto_pair_no')
async def add_auto_pair_no(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    ok, limit = await _check_pair_limit(repo, db_user)
    if not ok:
        await update_flow_message(callback.bot, state, callback.message.chat.id, t(language, 'pair_limit_reached', limit=limit), pair_no_keyboard(language))
        return
    pair_no = await repo.get_next_pair_no(db_user.id)
    await state.update_data(pair_no=pair_no)
    await _show_style(callback, state, language)


@router.message(AddPairStates.waiting_pair_no)
async def add_pair_no_text(message: Message, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    text = (message.text or '').strip()
    if not text.isdigit() or int(text) <= 0:
        await update_flow_message(message.bot, state, message.chat.id, t(language, 'invalid_pair_no'), pair_no_keyboard(language))
        return
    ok, limit = await _check_pair_limit(repo, db_user)
    if not ok:
        await update_flow_message(message.bot, state, message.chat.id, t(language, 'pair_limit_reached', limit=limit), pair_no_keyboard(language))
        return
    pair_no = int(text)
    if await repo.get_pair_by_no(db_user.id, pair_no):
        await update_flow_message(message.bot, state, message.chat.id, t(language, 'pair_no_exists', pair_no=pair_no), pair_no_keyboard(language))
        return
    await state.update_data(pair_no=pair_no)
    await _show_style(message, state, language)


@router.callback_query(AddPairStates.waiting_style, F.data.startswith('add:style:'))
async def add_style(callback: CallbackQuery, state: FSMContext, language: str) -> None:
    await callback.answer()
    style = callback.data.split(':')[-1]
    if style not in {'random', 'by_order'}:
        style = 'random'
    await state.update_data(repost_style=style)
    await _show_channels(callback, state, language)


@router.message(AddPairStates.waiting_channels)
async def add_channels(message: Message, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    raw = (message.text or '').strip()
    data = await state.get_data()
    style = data.get('repost_style', 'random')
    ok, error_text, channels = await _validate_and_resolve_channels(
        message.bot, repo, db_user, language, raw, by_order=style == 'by_order'
    )
    await state.update_data(raw_channels=raw)
    if not ok:
        await state.set_state(AddPairStates.admin_missing)
        await update_flow_message(message.bot, state, message.chat.id, error_text or t(language, 'generic_error'), recheck_keyboard(language, 'add'))
        return
    await state.update_data(channels=channels)
    await _show_movie(message, state, language)


@router.callback_query(AddPairStates.admin_missing, F.data == 'add:recheck_admin')
async def add_recheck(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    data = await state.get_data()
    raw = data.get('raw_channels', '')
    style = data.get('repost_style', 'random')
    ok, error_text, channels = await _validate_and_resolve_channels(
        callback.bot, repo, db_user, language, raw, by_order=style == 'by_order'
    )
    if not ok:
        await update_flow_message(callback.bot, state, callback.message.chat.id, error_text or t(language, 'generic_error'), recheck_keyboard(language, 'add'))
        return
    await state.update_data(channels=channels)
    await _show_movie(callback, state, language)


@router.callback_query(AddPairStates.waiting_movie_rule, F.data.startswith('add:movie:'))
async def add_movie(callback: CallbackQuery, state: FSMContext, language: str) -> None:
    await callback.answer()
    value = callback.data.split(':')[-1]
    await state.update_data(movie_rule=value == 'on')
    await _show_confirm(callback, state, language)


@router.callback_query(AddPairStates.confirmation, F.data == 'add:confirm')
async def add_confirm(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    data = await state.get_data()
    try:
        if await repo.get_pair_by_no(db_user.id, int(data['pair_no'])):
            await update_flow_message(callback.bot, state, callback.message.chat.id, t(language, 'pair_no_exists', pair_no=data['pair_no']), pair_no_keyboard(language))
            await state.set_state(AddPairStates.waiting_pair_no)
            return
        pair = await repo.create_pair(
            user_id=db_user.id,
            pair_no=int(data['pair_no']),
            repost_style=data.get('repost_style', 'random'),
            movie_rule=bool(data.get('movie_rule')),
            channels=data['channels'],
        )
        await update_flow_message(
            callback.bot,
            state,
            callback.message.chat.id,
            t(language, 'pair_created', pair_no=pair.pair_no),
            None,
        )
        await state.clear()
        await callback.message.answer(t(language, 'main_menu'), reply_markup=main_menu(language))
    except Exception:
        logger.exception('add pair confirm failed', extra={'user_id': db_user.tg_user_id})
        await update_flow_message(callback.bot, state, callback.message.chat.id, t(language, 'generic_error'), None)
        await state.clear()
        await callback.message.answer(t(language, 'main_menu'), reply_markup=main_menu(language))


@router.callback_query(AddPairStates.waiting_style, F.data == 'flow:back')
async def add_back_to_pair_no(callback: CallbackQuery, state: FSMContext, language: str) -> None:
    await callback.answer()
    await _show_pair_no(callback, state, language)


@router.callback_query(AddPairStates.waiting_channels, F.data == 'flow:back')
@router.callback_query(AddPairStates.admin_missing, F.data == 'flow:back')
async def add_back_to_style(callback: CallbackQuery, state: FSMContext, language: str) -> None:
    await callback.answer()
    await _show_style(callback, state, language)


@router.callback_query(AddPairStates.waiting_movie_rule, F.data == 'flow:back')
async def add_back_to_channels(callback: CallbackQuery, state: FSMContext, language: str) -> None:
    await callback.answer()
    await _show_channels(callback, state, language)


@router.callback_query(AddPairStates.confirmation, F.data == 'flow:back')
async def add_back_to_movie(callback: CallbackQuery, state: FSMContext, language: str) -> None:
    await callback.answer()
    await _show_movie(callback, state, language)
