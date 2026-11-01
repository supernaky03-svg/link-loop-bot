from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
import ast

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
    subprocess.run([sys.executable, str(ROOT / "apply_loop_dedupe_rollback_fix.py")], cwd=ROOT, check=True)
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
    tree = ast.parse(repository)
    repo_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Repository")
    for method_name in ("mark_processed", "create_loop_state", "save_loop_event"):
        method = next(
            (node for node in repo_class.body if isinstance(node, ast.AsyncFunctionDef) and node.name == method_name),
            None,
        )
        if method is None:
            raise SystemExit(f"Missing Repository.{method_name}()")
        calls = {
            node.func.attr for node in ast.walk(method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        if "on_conflict_do_nothing" not in calls or "rollback" in calls:
            raise SystemExit(f"Rollback-safe dedupe guard failed: Repository.{method_name}()")
    print("All upstream repost fixes, Mini App integration, Pair initialization, and rollback-safe dedupe fixes applied.")


if __name__ == "__main__":
    main()
