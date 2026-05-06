from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddPairStates(StatesGroup):
    waiting_pair_no = State()
    waiting_style = State()
    waiting_channels = State()
    waiting_channel_missing = State()
    waiting_movie_rule = State()
    admin_missing = State()
    confirmation = State()


class RemovePairStates(StatesGroup):
    selecting_pair = State()
    confirmation = State()


class EditStyleStates(StatesGroup):
    selecting_pair = State()
    waiting_style = State()
    waiting_order = State()


class EditMovieStates(StatesGroup):
    selecting_pair = State()
    waiting_value = State()


class LanguageStates(StatesGroup):
    choosing = State()
