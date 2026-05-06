from __future__ import annotations

from aiogram import Dispatcher

from app.bot.handlers import admin, channel_posts, menu, pair_add, pair_edit, pair_remove, permissions, start


def register_handlers(dp: Dispatcher) -> None:
    # Admin commands first, then normal commands/menu, then channel updates.
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(pair_add.router)
    dp.include_router(pair_remove.router)
    dp.include_router(pair_edit.router)
    dp.include_router(menu.router)
    dp.include_router(channel_posts.router)
    dp.include_router(permissions.router)
