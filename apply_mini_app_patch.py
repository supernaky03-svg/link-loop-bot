from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    if new in source:
        return
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one patch target in {path}, found {count}: {old!r}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def patch_config() -> None:
    path = ROOT / "app/config.py"
    replace_once(path, "    admin_contact: str = '@mnsm6003'\n", "    admin_contact: str = '@mnsm6003'\n    mini_app_url: str = ''\n")
    replace_once(
        path,
        "        admin_contact=os.getenv('ADMIN_CONTACT', '@mnsm6003'),\n",
        "        admin_contact=os.getenv('ADMIN_CONTACT', '@mnsm6003'),\n"
        "        mini_app_url=os.getenv('MINI_APP_URL', '').strip(),\n",
    )


def patch_models() -> None:
    path = ROOT / "app/db/models.py"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.lstrip().startswith("pairs: Mapped[list[") and "= relationship(" in line:
            # Check the whole relationship block so this patch remains idempotent.
            block = "".join(lines[index:index + 5])
            if "lazy=" not in block:
                lines[index] = (
                    '    # Explicit eager loading prevents implicit async IO (MissingGreenlet).\n'
                    '    pairs: Mapped[list["Pair"]] = relationship(\n'
                    '        back_populates="user", cascade="all, delete-orphan", lazy="selectin"\n'
                    '    )\n'
                )
            path.write_text("".join(lines), encoding="utf-8")
            return
    raise RuntimeError(f"Could not find User.pairs relationship in {path}")


def patch_main() -> None:
    path = ROOT / "app/main.py"
    replace_once(path, "    health_runner = await start_health_server(settings)\n", "    health_runner = await start_health_server(settings, bot)\n")


def patch_health() -> None:
    (ROOT / "app/health.py").write_text(
        "from __future__ import annotations\n\n"
        "from aiohttp import web\n\n"
        "from app.config import Settings\n"
        "from app.webapp import create_web_app\n\n\n"
        "async def start_health_server(settings: Settings, bot) -> web.AppRunner:\n"
        "    app = create_web_app(settings, bot)\n"
        "    runner = web.AppRunner(app)\n"
        "    await runner.setup()\n"
        "    site = web.TCPSite(runner, settings.health_host, settings.port)\n"
        "    await site.start()\n"
        "    return runner\n",
        encoding="utf-8",
    )


def patch_reply_keyboard() -> None:
    (ROOT / "app/bot/keyboards/reply.py").write_text(
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
        "        rows.insert(0, [KeyboardButton(text=b(language, 'web_app'))])\n"
        "    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder=b(language, 'help'))\n",
        encoding="utf-8",
    )


def patch_locales() -> None:
    replace_once(ROOT / "app/bot/locales/en.py", "    'help': '❓ Help',\n", "    'help': '❓ Help',\n    'web_app': '📱 Open Mini App',\n")
    replace_once(ROOT / "app/bot/locales/my.py", "    'help': '❓ အကူအညီ',\n", "    'help': '❓ အကူအညီ',\n    'web_app': '📱 Mini App ဖွင့်မယ်',\n")


def patch_env_example() -> None:
    path = ROOT / ".env.example"
    source = path.read_text(encoding="utf-8")
    if "MINI_APP_URL=" not in source:
        source += "\n# Public HTTPS URL served by this Render service\nMINI_APP_URL=https://YOUR-RENDER-SERVICE.onrender.com/app\n"
        path.write_text(source, encoding="utf-8")


def main() -> None:
    required = [
        ROOT / "app/config.py", ROOT / "app/db/models.py", ROOT / "app/main.py",
        ROOT / ".env.example", ROOT / "app/webapp.py", ROOT / "app/webapp_auth.py",
        ROOT / "app/web/index.html",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing required files: " + ", ".join(missing))
    patch_config()
    patch_models()
    patch_main()
    patch_health()
    patch_reply_keyboard()
    patch_locales()
    patch_env_example()
    print("Mini App integration applied. Configure MINI_APP_URL on Render.")


if __name__ == "__main__":
    main()
