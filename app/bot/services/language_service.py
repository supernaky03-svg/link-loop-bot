from __future__ import annotations

from app.bot.locales.en import BUTTONS as EN_BUTTONS, TEXTS as EN_TEXTS
from app.bot.locales.my import BUTTONS as MY_BUTTONS, TEXTS as MY_TEXTS

TEXT_MAP = {'en': EN_TEXTS, 'my': MY_TEXTS}
BUTTON_MAP = {'en': EN_BUTTONS, 'my': MY_BUTTONS}


def normalize_lang(language: str | None) -> str:
    return language if language in TEXT_MAP else 'en'


def t(language: str | None, key: str, **kwargs) -> str:
    lang = normalize_lang(language)
    template = TEXT_MAP[lang].get(key, EN_TEXTS.get(key, key))
    return template.format(**kwargs) if kwargs else template


def b(language: str | None, key: str) -> str:
    lang = normalize_lang(language)
    return BUTTON_MAP[lang].get(key, EN_BUTTONS.get(key, key))
