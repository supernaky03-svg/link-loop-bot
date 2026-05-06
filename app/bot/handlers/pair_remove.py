from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.inline import confirm_keyboard, flow_nav_keyboard, pair_select_keyboard
from app.bot.keyboards.reply import main_menu
from app.bot.services.flow_message import update_flow_message
from app.bot.services.language_service import b, t
from app.bot.services.pair_service import pair_details
from app.bot.states.pair_states import RemovePairStates
from app.db.models import User
from app.db.repository import Repository

logger = logging.getLogger(__name__)
router = Router(name='pair_remove')


def _buttons() -> set[str]:
    return {b('en', 'remove_pair'), b('my', 'remove_pair')}


async def _show_select(message_or_callback, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    pairs = await repo.get_user_pairs(db_user.id, active_only=True)
    chat_id = message_or_callback.message.chat.id if isinstance(message_or_callback, CallbackQuery) else message_or_callback.chat.id
    bot = message_or_callback.bot
    if not pairs:
        await update_flow_message(bot, state, chat_id, t(language, 'no_pairs'), flow_nav_keyboard(language, back=False))
        return
    await state.set_state(RemovePairStates.selecting_pair)
    await update_flow_message(
        bot,
        state,
        chat_id,
        t(language, 'select_pair_remove'),
        pair_select_keyboard(language, [p.pair_no for p in pairs], 'remove'),
    )


@router.message(F.text.in_(_buttons()))
async def begin_remove(message: Message, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await state.clear()
    await _show_select(message, state, repo, db_user, language)


@router.callback_query(RemovePairStates.selecting_pair, F.data.startswith('remove:pair:'))
async def select_remove_pair(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    pair_no = int(callback.data.split(':')[-1])
    pair = await repo.get_pair_by_no(db_user.id, pair_no)
    if not pair or not pair.is_active:
        await _show_select(callback, state, repo, db_user, language)
        return
    await state.update_data(pair_no=pair_no)
    await state.set_state(RemovePairStates.confirmation)
    await update_flow_message(
        callback.bot,
        state,
        callback.message.chat.id,
        t(language, 'remove_pair_confirm', details=pair_details(pair)),
        confirm_keyboard(language, 'remove'),
    )


@router.callback_query(RemovePairStates.confirmation, F.data == 'remove:confirm')
async def confirm_remove(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    data = await state.get_data()
    pair = await repo.get_pair_by_no(db_user.id, int(data['pair_no']))
    if pair:
        await repo.remove_pair(pair, hard_delete=False)
    await update_flow_message(
        callback.bot,
        state,
        callback.message.chat.id,
        t(language, 'pair_removed', pair_no=data['pair_no']),
        None,
    )
    await state.clear()
    await callback.message.answer(t(language, 'main_menu'), reply_markup=main_menu(language))


@router.callback_query(RemovePairStates.confirmation, F.data == 'flow:back')
async def remove_back(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    await _show_select(callback, state, repo, db_user, language)
