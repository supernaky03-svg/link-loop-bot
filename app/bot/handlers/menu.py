from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.inline import language_keyboard
from app.bot.keyboards.reply import main_menu
from app.bot.services.flow_message import update_flow_message
from app.bot.services.language_service import b, t
from app.bot.services.pair_service import pair_details
from app.bot.states.pair_states import LanguageStates
from app.config import get_settings
from app.db.models import User
from app.db.repository import Repository

router = Router(name='menu')


def _all_button_keys(key: str) -> set[str]:
    return {b('en', key), b('my', key)}


@router.callback_query(F.data == 'flow:cancel')
async def cancel_flow(callback: CallbackQuery, state: FSMContext, db_user: User, language: str) -> None:
    await callback.answer()
    if callback.message:
        await update_flow_message(callback.bot, state, callback.message.chat.id, t(language, 'cancelled'), None)
        await state.clear()
        await callback.message.answer(t(language, 'main_menu'), reply_markup=main_menu(db_user.language))
    else:
        await state.clear()


@router.message(F.text.in_(_all_button_keys('language')))
async def language_menu(message: Message, state: FSMContext, language: str) -> None:
    await state.clear()
    await state.set_state(LanguageStates.choosing)
    await update_flow_message(message.bot, state, message.chat.id, t(language, 'choose_language'), language_keyboard(language))


@router.callback_query(F.data.startswith('language:set:'))
async def set_language(callback: CallbackQuery, repo: Repository, db_user: User, state: FSMContext) -> None:
    lang = callback.data.split(':')[-1]
    if lang not in {'en', 'my'}:
        lang = 'en'
    await repo.update_user_language(db_user, lang)
    await callback.answer(t(lang, 'language_saved'))
    if callback.message:
        await update_flow_message(callback.bot, state, callback.message.chat.id, t(lang, 'language_saved'), None)
        await state.clear()
        await callback.message.answer(t(lang, 'main_menu'), reply_markup=main_menu(lang))
    else:
        await state.clear()


@router.message(F.text.in_(_all_button_keys('contact_admin')))
async def contact_admin(message: Message, language: str) -> None:
    settings = get_settings()
    await message.answer(t(language, 'contact_admin', admin_contact=settings.admin_contact))


@router.message(F.text.in_(_all_button_keys('help')))
async def help_message(message: Message, language: str) -> None:
    await message.answer(t(language, 'help'))


@router.message(F.text.in_(_all_button_keys('my_pairs')))
async def my_pairs(message: Message, repo: Repository, db_user: User, language: str) -> None:
    pairs = await repo.get_user_pairs(db_user.id, active_only=True)
    if not pairs:
        await message.answer(t(language, 'no_pairs'))
        return

    text = '\n\n'.join(pair_details(pair) for pair in pairs)
    await message.answer(t(language, 'my_pairs', pairs=text))
