from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str, *, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if new in source:
        return
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one patch target in {path.relative_to(ROOT)}, found {count}. "
            "No source was changed for this patch target. Check the repository branch/version."
        )
    path.write_text(source.replace(old, new, 1), encoding="utf-8")



def patch_register_handlers_export() -> None:
    # The repository's reliability overlay contains an empty handlers/__init__.py,
    # while app.main imports register_handlers from this package. Restore the router
    # registration explicitly so reapplying the all-in-one overlay cannot reintroduce
    # the Render startup ImportError.
    path = ROOT / "app/bot/handlers/__init__.py"
    path.write_text(
        "from __future__ import annotations\n\n"
        "from aiogram import Dispatcher\n\n"
        "from . import admin, channel_posts, menu, pair_add, pair_edit, pair_remove, permissions, start\n\n\n"
        "def register_handlers(dp: Dispatcher) -> None:\n"
        "    # Register command/admin handlers before channel-post processing.\n"
        "    dp.include_router(admin.router)\n"
        "    dp.include_router(start.router)\n"
        "    # Main-menu buttons (including Mini App) must run before state-wide\n"
        "    # text-input handlers, so they are not consumed as channel input.\n"
        "    dp.include_router(menu.router)\n"
        "    dp.include_router(pair_add.router)\n"
        "    dp.include_router(pair_remove.router)\n"
        "    dp.include_router(pair_edit.router)\n"
        "    dp.include_router(channel_posts.router)\n"
        "    dp.include_router(permissions.router)\n",
        encoding="utf-8",
    )

def patch_repository_pair_creation() -> None:
    path = ROOT / "app/db/repository.py"
    source = path.read_text(encoding="utf-8")
    old = """                is_active=True,
                is_paused=False,
            )
            self.session.add(pair)
"""
    new = """                is_active=True,
                is_paused=False,
                # Initialize the collection before flush. Accessing an unset async
                # relationship after flush can trigger forbidden implicit IO
                # (MissingGreenlet) when pair.channels.append(...) is called.
                channels=[],
            )
            self.session.add(pair)
"""
    replace_once(path, old, new, label="MissingGreenlet Pair.channels initialization")


def patch_pair_add_rollback() -> None:
    path = ROOT / "app/bot/handlers/pair_add.py"
    source = path.read_text(encoding="utf-8")
    old = """    except Exception:
        logger.exception('add pair confirm failed', extra={'user_id': db_user.tg_user_id})
        await update_flow_message(callback.bot, state, callback.message.chat.id, t(language, 'generic_error'), None)
        await state.clear()
        await callback.message.answer(t(language, 'main_menu'), reply_markup=main_menu(language))
"""
    new = """    except Exception:
        logger.exception('add pair confirm failed', extra={'user_id': db_user.tg_user_id})
        # Recover the AsyncSession after a failed flush/commit. Keep the FSM in
        # confirmation state so a transient DB failure can be retried safely.
        try:
            await repo.session.rollback()
        except Exception:
            logger.exception('add pair confirm rollback failed', extra={'user_id': db_user.tg_user_id})
        await state.set_state(AddPairStates.confirmation)
        await update_flow_message(
            callback.bot,
            state,
            callback.message.chat.id,
            t(language, 'generic_error'),
            confirm_keyboard(language, 'add'),
        )
        return
"""
    replace_once(path, old, new, label="Pair confirmation rollback and retry keyboard")

    source = path.read_text(encoding="utf-8")
    if "from app.bot.keyboards.inline import (" in source:
        if "    confirm_keyboard," in source:
            return
    # Current upstream imports confirm_keyboard in a grouped import; this should
    # already be available. Fail loudly if the file shape differs unexpectedly.
    if "    confirm_keyboard," not in source:
        raise RuntimeError("Could not verify confirm_keyboard import in pair_add.py")


def patch_reply_keyboard() -> None:
    path = ROOT / "app/bot/keyboards/reply.py"
    path.write_text(
        "from __future__ import annotations\n\n"
        "from aiogram.types import KeyboardButton, ReplyKeyboardMarkup\n\n"
        "from app.bot.services.language_service import b\n"
        "from app.config import get_settings\n\n\n"
        "def main_menu(language: str) -> ReplyKeyboardMarkup:\n"
        "    rows = [\n"
        "        [KeyboardButton(text=b(language, 'add_pair')), KeyboardButton(text=b(language, 'remove_pair'))],\n"
        "        [KeyboardButton(text=b(language, 'edit_style')), KeyboardButton(text=b(language, 'edit_movie'))],\n"
        "        [KeyboardButton(text=b(language, 'my_pairs')), KeyboardButton(text=b(language, 'language'))],\n"
        "        [KeyboardButton(text=b(language, 'contact_admin')), KeyboardButton(text=b(language, 'help'))],\n"
        "    ]\n"
        "    if get_settings().mini_app_url.strip().startswith('https://'):\n"
        "        # This is intentionally a plain reply-keyboard text button. The bot\n"
        "        # responds with an inline WebAppInfo button in the private chat.\n"
        "        rows.insert(0, [KeyboardButton(text=b(language, 'web_app'))])\n"
        "    return ReplyKeyboardMarkup(\n"
        "        keyboard=rows,\n"
        "        resize_keyboard=True,\n"
        "        input_field_placeholder=b(language, 'help'),\n"
        "    )\n",
        encoding="utf-8",
    )


def patch_inline_keyboard() -> None:
    path = ROOT / "app/bot/keyboards/inline.py"
    source = path.read_text(encoding="utf-8")
    if "WebAppInfo" not in source:
        source = source.replace(
            "from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup\n",
            "from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo\n",
            1,
        )
    if "from app.bot.services.language_service import t\n" in source:
        source = source.replace(
            "from app.bot.services.language_service import t\n",
            "from app.bot.services.language_service import b, t\n",
            1,
        )
    if "def mini_app_launch_keyboard(" not in source:
        source += "\n\n\ndef mini_app_launch_keyboard(language: str, url: str) -> InlineKeyboardMarkup:\n" \
                  "    return InlineKeyboardMarkup(\n" \
                  "        inline_keyboard=[[\n" \
                  "            InlineKeyboardButton(\n" \
                  "                text=b(language, 'web_app'),\n" \
                  "                web_app=WebAppInfo(url=url),\n" \
                  "            )\n" \
                  "        ]]\n" \
                  "    )\n"
    if "WebAppInfo" not in source or "import b, t" not in source:
        raise RuntimeError("Could not apply Mini App inline keyboard imports")
    path.write_text(source, encoding="utf-8")


def patch_menu_handler() -> None:
    path = ROOT / "app/bot/handlers/menu.py"
    source = path.read_text(encoding="utf-8")
    old_import = "from app.bot.keyboards.inline import language_keyboard\n"
    new_import = "from app.bot.keyboards.inline import language_keyboard, mini_app_launch_keyboard\n"
    if new_import not in source:
        if old_import not in source:
            raise RuntimeError("Could not find language_keyboard import in menu.py")
        source = source.replace(old_import, new_import, 1)

    marker = "def _all_button_keys(key: str) -> set[str]:\n    return {b('en', key), b('my', key)}\n"
    handler = marker + "\n\n@router.message(F.text.in_(_all_button_keys('web_app')))\n" \
        "async def open_mini_app(message: Message, language: str) -> None:\n" \
        "    url = get_settings().mini_app_url.strip()\n" \
        "    if not url.startswith('https://'):\n" \
        "        await message.answer('Mini App URL is not configured.')\n" \
        "        return\n" \
        "    prompt = (\n" \
        "        'Tap the button below to open the Mini App.'\n" \
        "        if language == 'en'\n" \
        "        else 'အောက်ပါ Inline Button ကိုနှိပ်ပြီး Mini App ကိုဖွင့်ပါ။'\n" \
        "    )\n" \
        "    await message.answer(\n" \
        "        prompt,\n" \
        "        reply_markup=mini_app_launch_keyboard(language, url),\n" \
        "    )\n"
    if "async def open_mini_app(" not in source:
        if source.count(marker) != 1:
            raise RuntimeError("Could not locate menu button helper for Mini App handler")
        source = source.replace(marker, handler, 1)
    path.write_text(source, encoding="utf-8")


def main() -> None:
    required = [
        ROOT / "app/db/repository.py",
        ROOT / "app/bot/handlers/pair_add.py",
        ROOT / "app/bot/handlers/__init__.py",
        ROOT / "app/bot/keyboards/reply.py",
        ROOT / "app/bot/keyboards/inline.py",
        ROOT / "app/bot/handlers/menu.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        raise SystemExit("Required source files are missing: " + ", ".join(missing))

    patch_register_handlers_export()
    patch_repository_pair_creation()
    patch_pair_add_rollback()
    patch_reply_keyboard()
    patch_inline_keyboard()
    patch_menu_handler()
    print("Applied Pair MissingGreenlet fix, failed-transaction rollback, and inline Mini App launch UX.")


if __name__ == "__main__":
    main()
