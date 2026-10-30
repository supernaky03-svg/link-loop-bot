import ast
from pathlib import Path


def test_handlers_package_exports_register_handlers():
    source = Path("app/bot/handlers/__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "register_handlers"
        for node in tree.body
    )
