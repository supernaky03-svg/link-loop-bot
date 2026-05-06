from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.keyboards.reply import main_menu
from app.bot.services.language_service import t
from app.db.models import User

router = Router(name='start')


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, language: str) -> None:
    await message.answer(t(language, 'welcome'), reply_markup=main_menu(db_user.language))
