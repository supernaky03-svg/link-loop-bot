from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards.inline import flow_nav_keyboard, pair_select_keyboard
from app.bot.services.flow_message import update_flow_message
from app.bot.services.language_service import b, t
from app.bot.services.pair_channel_service import ChannelManagementError, add_channel_to_pair, remove_channel_from_pair
from app.config import get_settings
from app.db.models import Pair, User
from app.db.repository import Repository

logger = logging.getLogger(__name__)
router = Router(name="channel_management")


class ManageChannelsStates(StatesGroup):
    selecting_pair = State()
    selecting_action = State()
    waiting_add_channel = State()
    selecting_remove_channel = State()
    confirming_remove = State()


def _manage_buttons() -> set[str]:
    return {b("en", "manage_channels"), b("my", "manage_channels")}


def _chat_id(event: Message | CallbackQuery) -> int:
    if isinstance(event, CallbackQuery):
        return event.message.chat.id if event.message else 0
    return event.chat.id


def _bot(event: Message | CallbackQuery):
    return event.bot


def _action_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(language, "manage_add_channel"), callback_data="cm:action:add"),
                InlineKeyboardButton(text=t(language, "manage_remove_channel"), callback_data="cm:action:remove"),
            ],
            *flow_nav_keyboard(language, back=False).inline_keyboard,
        ]
    )


def _remove_keyboard(pair: Pair, language: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{ch.order_no}. {ch.title[:38]}",
            callback_data=f"cm:remove:{ch.chat_id}",
        )]
        for ch in sorted((c for c in pair.channels if c.is_active), key=lambda c: c.order_no)
    ]
    rows += flow_nav_keyboard(language, back=False).inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language, "confirm"), callback_data="cm:confirm_remove")],
            [InlineKeyboardButton(text=t(language, "cancel"), callback_data="cm:cancel_remove")],
        ]
    )


async def _show_pair_action(
    event: Message | CallbackQuery,
    state: FSMContext,
    repo: Repository,
    user: User,
    language: str,
    pair_no: int,
) -> None:
    pair = await repo.get_pair_by_no(user.id, pair_no)
    if not pair:
        await state.clear()
        await update_flow_message(_bot(event), state, _chat_id(event), t(language, "pair_not_found"), None)
        return
    active = [ch for ch in pair.channels if ch.is_active]
    channel_lines = "\n".join(f"{ch.order_no}. {ch.title} ({ch.chat_id})" for ch in sorted(active, key=lambda c: c.order_no))
    summary = t(
        language,
        "manage_pair_summary",
        pair_no=pair.pair_no,
        count=len(active),
        channels=channel_lines or t(language, "manage_no_active_channels"),
    )
    await state.update_data(pair_no=pair_no)
    await state.set_state(ManageChannelsStates.selecting_action)
    await update_flow_message(_bot(event), state, _chat_id(event), summary, _action_keyboard(language))


async def _show_pair_selection(
    event: Message | CallbackQuery,
    state: FSMContext,
    repo: Repository,
    user: User,
    language: str,
) -> None:
    pairs = await repo.get_user_pairs(user.id, active_only=True)
    if not pairs:
        await state.clear()
        await update_flow_message(_bot(event), state, _chat_id(event), t(language, "no_pairs"), flow_nav_keyboard(language, back=False))
        return
    await state.set_state(ManageChannelsStates.selecting_pair)
    await update_flow_message(
        _bot(event), state, _chat_id(event), t(language, "manage_select_pair"),
        pair_select_keyboard(language, [p.pair_no for p in pairs], "cm"),
    )


@router.message(F.text.in_(_manage_buttons()))
async def begin_channel_management(
    message: Message, state: FSMContext, repo: Repository, db_user: User, language: str
) -> None:
    await state.clear()
    await _show_pair_selection(message, state, repo, db_user, language)


@router.callback_query(ManageChannelsStates.selecting_pair, F.data.startswith("cm:pair:"))
async def choose_pair(
    callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str
) -> None:
    await callback.answer()
    pair_no = int(callback.data.rsplit(":", 1)[-1])
    await _show_pair_action(callback, state, repo, db_user, language, pair_no)


@router.callback_query(ManageChannelsStates.selecting_action, F.data == "cm:action:add")
async def begin_add_channel(callback: CallbackQuery, state: FSMContext, language: str) -> None:
    await callback.answer()
    await state.set_state(ManageChannelsStates.waiting_add_channel)
    await update_flow_message(
        callback.bot, state, _chat_id(callback), t(language, "manage_add_prompt"),
        flow_nav_keyboard(language, back=False),
    )


@router.message(ManageChannelsStates.waiting_add_channel)
async def receive_channel_to_add(
    message: Message, state: FSMContext, repo: Repository, db_user: User, language: str
) -> None:
    data = await state.get_data()
    pair_no = int(data.get("pair_no", 0))
    pair = await repo.get_pair_by_no(db_user.id, pair_no)
    if not pair:
        await _show_pair_selection(message, state, repo, db_user, language)
        return
    try:
        await add_channel_to_pair(message.bot, repo, db_user, pair, message.text or "", get_settings())
    except ChannelManagementError as exc:
        await update_flow_message(
            message.bot, state, message.chat.id,
            t(language, "manage_operation_error", error=str(exc)),
            flow_nav_keyboard(language, back=False),
        )
        return
    except Exception:
        logger.exception("add channel from bot failed", extra={"user_id": db_user.tg_user_id, "pair_no": pair_no})
        await update_flow_message(message.bot, state, message.chat.id, t(language, "generic_error"), flow_nav_keyboard(language, back=False))
        return
    await _show_pair_action(message, state, repo, db_user, language, pair_no)
    await message.answer(t(language, "manage_channel_added"))


@router.callback_query(ManageChannelsStates.selecting_action, F.data == "cm:action:remove")
async def begin_remove_channel(
    callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str
) -> None:
    await callback.answer()
    data = await state.get_data()
    pair = await repo.get_pair_by_no(db_user.id, int(data.get("pair_no", 0)))
    if not pair:
        await _show_pair_selection(callback, state, repo, db_user, language)
        return
    if not any(ch.is_active for ch in pair.channels):
        await _show_pair_action(callback, state, repo, db_user, language, pair.pair_no)
        return
    await state.set_state(ManageChannelsStates.selecting_remove_channel)
    await update_flow_message(
        callback.bot, state, _chat_id(callback), t(language, "manage_select_channel_remove"),
        _remove_keyboard(pair, language),
    )


@router.callback_query(ManageChannelsStates.selecting_remove_channel, F.data.startswith("cm:remove:"))
async def select_channel_to_remove(callback: CallbackQuery, state: FSMContext, language: str) -> None:
    await callback.answer()
    chat_id = int(callback.data.rsplit(":", 1)[-1])
    await state.update_data(remove_chat_id=chat_id)
    await state.set_state(ManageChannelsStates.confirming_remove)
    await update_flow_message(
        callback.bot, state, _chat_id(callback),
        t(language, "manage_confirm_remove", chat_id=chat_id), _confirm_keyboard(language),
    )


@router.callback_query(ManageChannelsStates.confirming_remove, F.data == "cm:cancel_remove")
async def cancel_remove_channel(callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str) -> None:
    await callback.answer()
    data = await state.get_data()
    await _show_pair_action(callback, state, repo, db_user, language, int(data.get("pair_no", 0)))


@router.callback_query(ManageChannelsStates.confirming_remove, F.data == "cm:confirm_remove")
async def confirm_remove_channel(
    callback: CallbackQuery, state: FSMContext, repo: Repository, db_user: User, language: str
) -> None:
    await callback.answer()
    data = await state.get_data()
    pair_no = int(data.get("pair_no", 0))
    pair = await repo.get_pair_by_no(db_user.id, pair_no)
    if not pair:
        await _show_pair_selection(callback, state, repo, db_user, language)
        return
    try:
        await remove_channel_from_pair(repo, db_user, pair, int(data["remove_chat_id"]))
    except ChannelManagementError as exc:
        await state.set_state(ManageChannelsStates.selecting_action)
        await update_flow_message(callback.bot, state, _chat_id(callback), t(language, "manage_operation_error", error=str(exc)), _action_keyboard(language))
        return
    except Exception:
        logger.exception("remove channel from bot failed", extra={"user_id": db_user.tg_user_id, "pair_no": pair_no})
        await state.set_state(ManageChannelsStates.selecting_action)
        await update_flow_message(callback.bot, state, _chat_id(callback), t(language, "generic_error"), _action_keyboard(language))
        return
    await _show_pair_action(callback, state, repo, db_user, language, pair_no)
