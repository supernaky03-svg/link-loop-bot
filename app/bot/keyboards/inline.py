from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.services.language_service import t


def flow_nav(language: str, *, back: bool = True, cancel: bool = True) -> list[list[InlineKeyboardButton]]:
    row: list[InlineKeyboardButton] = []
    if back:
        row.append(InlineKeyboardButton(text=t(language, 'back'), callback_data='flow:back'))
    if cancel:
        row.append(InlineKeyboardButton(text=t(language, 'cancel'), callback_data='flow:cancel'))
    return [row] if row else []


def flow_nav_keyboard(language: str, *, back: bool = True, cancel: bool = True) -> InlineKeyboardMarkup:
    """Shared Back/Cancel keyboard for text-input flow steps."""
    return InlineKeyboardMarkup(inline_keyboard=flow_nav(language, back=back, cancel=cancel))


def pair_no_keyboard(language: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=t(language, 'auto'), callback_data='add:auto_pair_no')]]
    rows += flow_nav(language, back=False)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def style_keyboard(language: str, prefix: str = 'add') -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=t(language, 'random'), callback_data=f'{prefix}:style:random'),
            InlineKeyboardButton(text=t(language, 'by_order'), callback_data=f'{prefix}:style:by_order'),
        ],
        *flow_nav(language),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def on_off_keyboard(language: str, prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=t(language, 'on'), callback_data=f'{prefix}:on'),
            InlineKeyboardButton(text=t(language, 'off'), callback_data=f'{prefix}:off'),
        ],
        *flow_nav(language),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard(language: str, prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(language, 'confirm'), callback_data=f'{prefix}:confirm')],
        *flow_nav(language),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def recheck_keyboard(language: str, prefix: str = 'add') -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(language, 'recheck'), callback_data=f'{prefix}:recheck_admin')],
        *flow_nav(language),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_keyboard(language: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text='English', callback_data='language:set:en'),
            InlineKeyboardButton(text='မြန်မာ', callback_data='language:set:my'),
        ],
        *flow_nav(language, back=False),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pair_select_keyboard(language: str, pair_numbers: list[int], prefix: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for pair_no in pair_numbers:
        row.append(InlineKeyboardButton(text=f'Pair {pair_no}', callback_data=f'{prefix}:pair:{pair_no}'))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows += flow_nav(language, back=False)
    return InlineKeyboardMarkup(inline_keyboard=rows)
