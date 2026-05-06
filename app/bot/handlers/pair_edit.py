from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.inline import flow_nav_keyboard, on_off_keyboard, pair_select_keyboard, style_keyboard
from app.bot.keyboards.reply import main_menu
from app.bot.services.flow_message import update_flow_message
from app.bot.services.language_service import b, t
from app.bot.states.pair_states import EditMovieStates, EditStyleStates
from app.db.models import Pair, User
from app.db.repository import Repository

logger = logging.getLogger(__name__)
router = Router(name='pair_edit')


def _style_buttons() -> set[str]:
    return {b('en', 'edit_style'), b('my', 'edit_style')}


def _movie_buttons() -> set[str]:
    return {b('en', 'edit_movie'), b('my', 'edit_movie')}


def _channels_lines(pair: Pair) -> str:
    return '\n'.join(f'{ch.order_no}. {ch.title} ({ch.chat_id})' for ch in sorted(pair.channels, key=lambda c: c.order_no))


def _parse_order(raw: str, pair: Pair) -> dict[int, int] | None:
    name_map: dict[str, int] = {}
    for ch in pair.channels:
        name_map[str(ch.chat_id)] = ch.chat_id
        name_map[ch.title.lower()] = ch.chat_id
        if ch.username:
            name_map[ch.username.lower().lstrip('@')] = ch.chat_id
            name_map['@' + ch.username.lower().lstrip('@')] = ch.chat_id
    result: dict[int, int] = {}
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    if len(parts) != len(pair.channels):
        return None
    for idx, part in enumerate(parts, start=1):
        order_no = idx
        value = part
        if '-' in part:
            maybe_no, maybe_value = part.split('-', 1)
            if maybe_no.strip().isdigit():
                order_no = int(maybe_no.strip())
                value = maybe_value.strip()
        chat_id = name_map.get(value.lower()) or (int(value) if value.lstrip('-').isdigit() else None)
        if chat_id is None:
            return None
        result[chat_id] = order_no
    return result if len(result) == len(pair.channels) else None


async def _select_pair(message_or_callback, state: FSMContext, repo: Repository, db_user: User, language: str, flow: str) -> None:
    pairs = await repo.get_user_pairs(db_user.id, active_only=True)
    chat_id = message_or_callback.message.chat.id if isinstance(message_or_callback, CallbackQuery) else message_or_callback.chat.id
    bot = message_or_callback.bot
    if flow == 'style':
        await state.set_state(EditStyleStates.selecting_pair)
        text = t(language, 'select_pair_style')
        prefix = 'editstyle'
    else:
        await state.set_state(EditMovieStates.selecting_pair)
        text = t(language, 'select_pair_movie')
        prefix = 'editmovie'
    if not pairs:
        await update_flow_message(bot, state, chat_id, t(language, 'no_pairs'), flow_nav_keyboard(language, back=False))
        return
    await update_flow_message(bot, state, chat_id, text, pair_select_keyboard(language, [p.pair_no for p in pairs], prefix))


async def _finish_flow(message_or_callback, state: FSMContext, language: str, text: str) -> None:
    chat_id = message_or_callback.message.chat.id if isinstance(message_or_callback, CallbackQuery) else message_or_callback.chat.id
    bot = message_or_callback.bot
    await update_flow_message(bot, state, chat_id, text, None)
    await state.clear()
    target_message = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    await target_message.answer(t(language, 'main_menu'), reply_markup=main_menu(language))


@router.message(F.text.in_(_style_buttons()))
async def begin_style(message: Message, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await state.clear()
    await _select_pair(message, state, repo, db_user, language, 'style')


@router.callback_query(EditStyleStates.selecting_pair, F.data.startswith('editstyle:pair:'))
async def select_style_pair(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    pair_no = int(callback.data.split(':')[-1])
    pair = await repo.get_pair_by_no(db_user.id, pair_no)
    if not pair:
        await _select_pair(callback, state, repo, db_user, language, 'style')
        return
    await state.update_data(pair_no=pair_no)
    await state.set_state(EditStyleStates.waiting_style)
    await update_flow_message(callback.bot, state, callback.message.chat.id, t(language, 'select_new_style', pair_no=pair_no), style_keyboard(language, 'editstyle'))


@router.callback_query(EditStyleStates.waiting_style, F.data.startswith('editstyle:style:'))
async def choose_new_style(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    style = callback.data.split(':')[-1]
    data = await state.get_data()
    pair = await repo.get_pair_by_no(db_user.id, int(data['pair_no']))
    if not pair:
        await _finish_flow(callback, state, language, t(language, 'generic_error'))
        return
    if style == 'random':
        await repo.update_pair_style(pair, 'random')
        await _finish_flow(callback, state, language, t(language, 'style_saved', pair_no=pair.pair_no))
        return
    await state.update_data(new_style='by_order')
    await state.set_state(EditStyleStates.waiting_order)
    await update_flow_message(
        callback.bot,
        state,
        callback.message.chat.id,
        t(language, 'send_new_order', channels=_channels_lines(pair)),
        flow_nav_keyboard(language),
    )


@router.message(EditStyleStates.waiting_order)
async def receive_new_order(message: Message, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    data = await state.get_data()
    pair = await repo.get_pair_by_no(db_user.id, int(data['pair_no']))
    if not pair:
        await _finish_flow(message, state, language, t(language, 'generic_error'))
        return
    order_map = _parse_order(message.text or '', pair)
    if not order_map:
        await update_flow_message(
            message.bot,
            state,
            message.chat.id,
            t(language, 'send_new_order', channels=_channels_lines(pair)),
            flow_nav_keyboard(language),
        )
        return
    await repo.update_pair_style(pair, 'by_order', order_map)
    await _finish_flow(message, state, language, t(language, 'style_saved', pair_no=pair.pair_no))


@router.message(F.text.in_(_movie_buttons()))
async def begin_movie(message: Message, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await state.clear()
    await _select_pair(message, state, repo, db_user, language, 'movie')


@router.callback_query(EditMovieStates.selecting_pair, F.data.startswith('editmovie:pair:'))
async def select_movie_pair(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    pair_no = int(callback.data.split(':')[-1])
    pair = await repo.get_pair_by_no(db_user.id, pair_no)
    if not pair:
        await _select_pair(callback, state, repo, db_user, language, 'movie')
        return
    await state.update_data(pair_no=pair_no)
    await state.set_state(EditMovieStates.waiting_value)
    await update_flow_message(callback.bot, state, callback.message.chat.id, t(language, 'add_pair_step_movie'), on_off_keyboard(language, 'editmovie:movie'))


@router.callback_query(EditMovieStates.waiting_value, F.data.startswith('editmovie:movie:'))
async def save_movie(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    value = callback.data.split(':')[-1] == 'on'
    data = await state.get_data()
    pair = await repo.get_pair_by_no(db_user.id, int(data['pair_no']))
    if pair:
        await repo.update_pair_movie_rule(pair, value)
    await _finish_flow(
        callback,
        state,
        language,
        t(language, 'movie_saved', pair_no=data['pair_no'], value=t(language, 'on' if value else 'off')),
    )


@router.callback_query(EditStyleStates.waiting_style, F.data == 'flow:back')
async def style_back_select(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    await _select_pair(callback, state, repo, db_user, language, 'style')


@router.callback_query(EditStyleStates.waiting_order, F.data == 'flow:back')
async def style_back_choice(callback: CallbackQuery, state: FSMContext, language: str) -> None:
    await callback.answer()
    data = await state.get_data()
    await state.set_state(EditStyleStates.waiting_style)
    await update_flow_message(callback.bot, state, callback.message.chat.id, t(language, 'select_new_style', pair_no=data['pair_no']), style_keyboard(language, 'editstyle'))


@router.callback_query(EditMovieStates.waiting_value, F.data == 'flow:back')
async def movie_back_select(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    await _select_pair(callback, state, repo, db_user, language, 'movie')
