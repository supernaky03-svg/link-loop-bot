from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def overlay(source: Path, target: Path) -> None:
    if not source.exists():
        raise SystemExit(f"Required upstream fix overlay is missing: {source}")
    shutil.copytree(source, target, dirs_exist_ok=True)


def main() -> None:
    overlay(ROOT / "link-loop-bot-fixed" / "app", ROOT / "app")
    overlay(ROOT / "link-loop-bot-fixed" / "tests", ROOT / "tests")
    subprocess.run([sys.executable, str(ROOT / "apply_mini_app_patch.py")], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "apply_pair_and_mini_launch_fix.py")], cwd=ROOT, check=True)
    models = (ROOT / "app/db/models.py").read_text(encoding="utf-8")
    repository = (ROOT / "app/db/repository.py").read_text(encoding="utf-8")
    reply = (ROOT / "app/bot/keyboards/reply.py").read_text(encoding="utf-8")
    menu = (ROOT / "app/bot/handlers/menu.py").read_text(encoding="utf-8")
    handlers_init = (ROOT / "app/bot/handlers/__init__.py").read_text(encoding="utf-8")
    if 'lazy="selectin"' not in models or 'channels=[]' not in repository:
        raise SystemExit("Async relationship initialization guard failed.")
    if "web_app=WebAppInfo" in reply or "async def open_mini_app" not in menu:
        raise SystemExit("Mini App inline-launch guard failed.")
    if "def register_handlers(" not in handlers_init:
        raise SystemExit("Bot handler registration export guard failed.")
    print("All upstream repost fixes, Mini App integration, and final hotfixes applied successfully.")


if __name__ == "__main__":
    main()
