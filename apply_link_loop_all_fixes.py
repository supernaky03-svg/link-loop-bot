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
    models = (ROOT / "app/db/models.py").read_text(encoding="utf-8")
    if 'lazy="selectin"' not in models or "pairs: Mapped[list[\"Pair\"]]" not in models:
        raise SystemExit("User.pairs eager-loading guard failed. Review app/db/models.py.")
    print("Combined Link Loop fixes and Mini App integration applied successfully.")


if __name__ == "__main__":
    main()
