from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.middlewares import DBSessionMiddleware, UserAccessMiddleware
from app.config import Settings


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    db = DBSessionMiddleware()
    access = UserAccessMiddleware(settings)

    dp.message.middleware(db)
    dp.callback_query.middleware(db)
    dp.channel_post.middleware(db)
    dp.my_chat_member.middleware(db)

    dp.message.middleware(access)
    dp.callback_query.middleware(access)
    return dp
