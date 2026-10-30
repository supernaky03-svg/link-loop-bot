from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.bot.services.language_service import b
from app.config import get_settings


def main_menu(language: str) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=b(language, 'add_pair')), KeyboardButton(text=b(language, 'remove_pair'))],
        [KeyboardButton(text=b(language, 'edit_style')), KeyboardButton(text=b(language, 'edit_movie'))],
        [KeyboardButton(text=b(language, 'my_pairs')), KeyboardButton(text=b(language, 'language'))],
        [KeyboardButton(text=b(language, 'contact_admin')), KeyboardButton(text=b(language, 'help'))],
    ]
    url = get_settings().mini_app_url
    if url.startswith('https://'):
        rows.insert(0, [KeyboardButton(text=b(language, 'web_app'), web_app=WebAppInfo(url=url))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder=b(language, 'help'))
