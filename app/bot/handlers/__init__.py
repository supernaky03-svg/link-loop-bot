from __future__ import annotations

from aiogram import Dispatcher

from . import admin, channel_posts, menu, pair_add, pair_edit, pair_remove, permissions, start


def register_handlers(dp: Dispatcher) -> None:
    # Register command/admin handlers before channel-post processing.
    dp.include_router(admin.router)
    dp.include_router(start.router)
    # Main-menu buttons (including Mini App) must run before state-wide
    # text-input handlers, so they are not consumed as channel input.
    dp.include_router(menu.router)
    dp.include_router(pair_add.router)
    dp.include_router(pair_remove.router)
    dp.include_router(pair_edit.router)
    dp.include_router(channel_posts.router)
    dp.include_router(permissions.router)
