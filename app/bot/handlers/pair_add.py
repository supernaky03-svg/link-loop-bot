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
from app.bot.services.channel_service import (
    ChannelCheckResult,
    ChannelValidationResult,
    merge_missing_channel_info,
    parse_channel_list,
    resolve_and_check_channel,
)
from app.bot.services.flow_message import update_flow_message
from app.bot.services.language_service import b, t
from app.bot.services.link_service import ParsedChannelInput
from app.bot.services.pair_service import user_limits
from app.bot.states.pair_states import AddPairStates
from app.config import get_settings
from app.db.models import User
from app.db.repository import Repository

logger = logging.getLogger(__name__)
router = Router(name='pair_add')


def _add_buttons() -> set[str]:
    return {b('en', 'add_pair'), b('my', 'add_pair')}


def _message_chat_id(message_or_callback: Message | CallbackQuery) -> int:
    if isinstance(message_or_callback, CallbackQuery):
        return message_or_callback.message.chat.id
    return message_or_callback.chat.id


def _message_bot(message_or_callback: Message | CallbackQuery):
    return message_or_callback.bot


async def _show_pair_no(message_or_callback, state: FSMContext, language: str) -> None:
    chat_id = _message_chat_id(message_or_callback)
    bot = _message_bot(message_or_callback)
    await state.set_state(AddPairStates.waiting_pair_no)
    await update_flow_message(bot, state, chat_id, t(language, 'add_pair_step_pair_no'), pair_no_keyboard(language))


async def _show_style(message_or_callback, state: FSMContext, language: str) -> None:
    chat_id = _message_chat_id(message_or_callback)
    bot = _message_bot(message_or_callback)
    await state.set_state(AddPairStates.waiting_style)
    await update_flow_message(bot, state, chat_id, t(language, 'add_pair_step_style'), style_keyboard(language, 'add'))


async def _show_channels(message_or_callback, state: FSMContext, language: str) -> None:
    data = await state.get_data()
    style = data.get('repost_style', 'random')
    key = 'add_pair_step_channels_order' if style == 'by_order' else 'add_pair_step_channels_random'
    chat_id = _message_chat_id(message_or_callback)
    bot = _message_bot(message_or_callback)
    await state.set_state(AddPairStates.waiting_channels)
    await update_flow_message(bot, state, chat_id, t(language, key), flow_nav_keyboard(language))


async def _show_missing_channel_info(message_or_callback, state: FSMContext, language: str) -> None:
    data = await state.get_data()
    inputs = _load_channel_inputs(data)
    chat_id = _message_chat_id(message_or_callback)
    bot = _message_bot(message_or_callback)
    await state.set_state(AddPairStates.waiting_channel_missing)
    await update_flow_message(bot, state, chat_id, _missing_channel_info_text(language, inputs), flow_nav_keyboard(language))


async def _show_movie(message_or_callback, state: FSMContext, language: str) -> None:
    chat_id = _message_chat_id(message_or_callback)
    bot = _message_bot(message_or_callback)
    await state.set_state(AddPairStates.waiting_movie_rule)
    await update_flow_message(bot, state, chat_id, t(language, 'add_pair_step_movie'), on_off_keyboard(language, 'add:movie'))


async def _show_confirm(message_or_callback, state: FSMContext, language: str) -> None:
    data = await state.get_data()
    channels = data.get('channels', [])
    channel_lines = '\n'.join(
        _format_channel_confirm_line(ch)
        for ch in sorted(channels, key=lambda x: x['order_no'])
    )
    text = t(
        language,
        'add_pair_confirm',
        pair_no=data['pair_no'],
        style=t(language, data['repost_style']),
        movie_rule=t(language, 'on' if data.get('movie_rule') else 'off'),
        channels=channel_lines,
    )
    chat_id = _message_chat_id(message_or_callback)
    bot = _message_bot(message_or_callback)
    await state.set_state(AddPairStates.confirmation)
    await update_flow_message(bot, state, chat_id, text, confirm_keyboard(language, 'add'))


def _format_channel_confirm_line(ch: dict) -> str:
    invite = ch.get('invite_link')
    suffix = f' | invite: {invite}' if invite else ''
    return f"{ch['order_no']}. {ch['title']} ({ch['chat_id']}){suffix}"


async def _check_pair_limit(repo: Repository, db_user: User) -> tuple[bool, int]:
    settings = get_settings()
    pair_limit, _ = await user_limits(repo, db_user, settings)
    current = await repo.count_active_pairs(db_user.id)
    return current < pair_limit, pair_limit


def _serialize_channel_inputs(inputs: list[ParsedChannelInput]) -> list[dict]:
    return [item.to_dict() for item in inputs]


def _load_channel_inputs(data: dict) -> list[ParsedChannelInput]:
    return [ParsedChannelInput.from_dict(item) for item in data.get('channel_inputs', [])]


def _missing_channel_info_text(language: str, inputs: list[ParsedChannelInput]) -> str:
    missing_id = [item for item in inputs if item.missing == 'chat_id']
    missing_invite = [item for item in inputs if item.missing == 'invite_link']
    parts: list[str] = []
    if missing_id:
        lines = [t(language, 'missing_chat_id_title')]
        for idx, item in enumerate(missing_id, start=1):
            lines.append(f'{idx}. {item.invite_link or item.raw}')
        lines.append('')
        lines.append(t(language, 'missing_chat_id_example'))
        parts.append('\n'.join(lines))
    if missing_invite:
        lines = [t(language, 'missing_invite_link_title')]
        for idx, item in enumerate(missing_invite, start=1):
            lines.append(f'{idx}. {item.chat_id or item.raw}')
        lines.append('')
        lines.append(t(language, 'missing_invite_link_example'))
        parts.append('\n'.join(lines))
    return '\n\n'.join(parts) if parts else t(language, 'generic_error')


def _invalid_channel_input_text(language: str, inputs: list[ParsedChannelInput]) -> str:
    invalids = [item.raw for item in inputs if item.error]
    lines = [t(language, 'invalid_channel_input_title')]
    for idx, raw in enumerate(invalids, start=1):
        lines.append(f'{idx}. {raw}')
    lines.append('')
    lines.append(t(language, 'channel_input_format_help'))
    return '\n'.join(lines)


async def _validate_and_resolve_inputs(
    bot,
    db_user: User,
    language: str,
    inputs: list[ParsedChannelInput],
    repo: Repository,
) -> ChannelValidationResult:
    settings = get_settings()
    _, channel_limit = await user_limits(repo, db_user, settings)
    if len(inputs) < 2 or len(inputs) > channel_limit:
        return ChannelValidationResult(False, [], t(language, 'channel_count_error', limit=channel_limit))

    invalids = [item for item in inputs if item.error]
    if invalids:
        return ChannelValidationResult(False, [], _invalid_channel_input_text(language, inputs), parsed_inputs=inputs)

    missing = [item for item in inputs if item.missing]
    if missing:
        return ChannelValidationResult(
            ok=False,
            channels=[],
            error_text=_missing_channel_info_text(language, inputs),
            needs_more_info=True,
            parsed_inputs=inputs,
        )

    checks: list[ChannelCheckResult] = []
    for item in inputs:
        checks.append(await resolve_and_check_channel(bot, item, item.order_no))

    resolved = [c for c in checks if c.chat_id is not None]
    ids = [c.chat_id for c in resolved]
    if len(ids) != len(set(ids)):
        return ChannelValidationResult(False, [], t(language, 'duplicate_channels'), parsed_inputs=inputs)

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
        return ChannelValidationResult(False, [], '\n'.join(lines), can_recheck=True, parsed_inputs=inputs)

    channels = [
        {
            'chat_id': int(c.chat_id),
            'title': c.title,
            'username': c.username,
            'channel_link': c.channel_link,
            'invite_link': c.invite_link,
            'order_no': int(c.order_no or idx),
        }
        for idx, c in enumerate(checks, start=1)
    ]
    return ChannelValidationResult(True, channels, parsed_inputs=inputs)


async def _validate_and_resolve_channels(
    bot,
    repo: Repository,
    db_user: User,
    language: str,
    raw: str,
    by_order: bool,
) -> ChannelValidationResult:
    inputs = parse_channel_list(raw, by_order)
    return await _validate_and_resolve_inputs(bot, db_user, language, inputs, repo)


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
    result = await _validate_and_resolve_channels(
        message.bot,
        repo,
        db_user,
        language,
        raw,
        by_order=style == 'by_order',
    )
    await state.update_data(
        raw_channels=raw,
        channel_inputs=_serialize_channel_inputs(result.parsed_inputs or []),
    )
    if not result.ok:
        if result.needs_more_info:
            await state.set_state(AddPairStates.waiting_channel_missing)
            await update_flow_message(
                message.bot,
                state,
                message.chat.id,
                result.error_text or t(language, 'generic_error'),
                flow_nav_keyboard(language),
            )
            return
        await state.set_state(AddPairStates.admin_missing if result.can_recheck else AddPairStates.waiting_channels)
        await update_flow_message(
            message.bot,
            state,
            message.chat.id,
            result.error_text or t(language, 'generic_error'),
            recheck_keyboard(language, 'add') if result.can_recheck else flow_nav_keyboard(language),
        )
        return
    await state.update_data(channels=result.channels)
    await _show_movie(message, state, language)


@router.message(AddPairStates.waiting_channel_missing)
async def add_missing_channel_info(message: Message, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    data = await state.get_data()
    inputs = _load_channel_inputs(data)
    inputs, changed = merge_missing_channel_info(inputs, (message.text or '').strip())
    if not changed:
        await update_flow_message(
            message.bot,
            state,
            message.chat.id,
            _missing_channel_info_text(language, inputs),
            flow_nav_keyboard(language),
        )
        return
    result = await _validate_and_resolve_inputs(message.bot, db_user, language, inputs, repo)
    await state.update_data(channel_inputs=_serialize_channel_inputs(result.parsed_inputs or inputs))
    if not result.ok:
        if result.needs_more_info:
            await update_flow_message(
                message.bot,
                state,
                message.chat.id,
                result.error_text or t(language, 'generic_error'),
                flow_nav_keyboard(language),
            )
            return
        await state.set_state(AddPairStates.admin_missing if result.can_recheck else AddPairStates.waiting_channel_missing)
        await update_flow_message(
            message.bot,
            state,
            message.chat.id,
            result.error_text or t(language, 'generic_error'),
            recheck_keyboard(language, 'add') if result.can_recheck else flow_nav_keyboard(language),
        )
        return
    await state.update_data(channels=result.channels)
    await _show_movie(message, state, language)


@router.callback_query(AddPairStates.admin_missing, F.data == 'add:recheck_admin')
async def add_recheck(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    data = await state.get_data()
    inputs = _load_channel_inputs(data)
    if not inputs:
        raw = data.get('raw_channels', '')
        style = data.get('repost_style', 'random')
        inputs = parse_channel_list(raw, by_order=style == 'by_order')
    result = await _validate_and_resolve_inputs(callback.bot, db_user, language, inputs, repo)
    await state.update_data(channel_inputs=_serialize_channel_inputs(result.parsed_inputs or inputs))
    if not result.ok:
        if result.needs_more_info:
            await state.set_state(AddPairStates.waiting_channel_missing)
            await update_flow_message(
                callback.bot,
                state,
                callback.message.chat.id,
                result.error_text or t(language, 'generic_error'),
                flow_nav_keyboard(language),
            )
            return
        await state.set_state(AddPairStates.admin_missing if result.can_recheck else AddPairStates.waiting_channels)
        await update_flow_message(
            callback.bot,
            state,
            callback.message.chat.id,
            result.error_text or t(language, 'generic_error'),
            recheck_keyboard(language, 'add') if result.can_recheck else flow_nav_keyboard(language),
        )
        return
    await state.update_data(channels=result.channels)
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
@router.callback_query(AddPairStates.waiting_channel_missing, F.data == 'flow:back')
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
