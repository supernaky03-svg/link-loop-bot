from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def update_flow_message(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> int | None:
    """Edit the saved flow message; send a new one if editing is impossible."""
    data = await state.get_data()
    message_id = data.get('flow_message_id')
    if message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return int(message_id)
        except TelegramBadRequest as exc:
            logger.info('flow edit failed; sending new flow message: %s', exc)
        except TelegramForbiddenError:
            logger.warning('cannot edit/send flow message; bot forbidden in chat_id=%s', chat_id)
            return None

    try:
        sent = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        await state.update_data(flow_message_id=sent.message_id)
        return sent.message_id
    except Exception:
        logger.exception('failed to send flow message', extra={'chat_id': chat_id})
        return None
