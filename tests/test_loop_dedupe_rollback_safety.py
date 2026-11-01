import ast
from pathlib import Path


def _repository_tree():
    source = Path("app/db/repository.py").read_text(encoding="utf-8")
    return ast.parse(source)


def _method(name: str):
    tree = _repository_tree()
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Repository")
    return next(
        node for node in cls.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )


def test_duplicate_guard_methods_use_postgres_conflict_handling():
    for name in ("mark_processed", "create_loop_state", "save_loop_event"):
        method = _method(name)
        attrs = {
            node.func.attr for node in ast.walk(method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "on_conflict_do_nothing" in attrs, name
        assert "rollback" not in attrs, name


def test_repository_imports_postgres_insert():
    source = Path("app/db/repository.py").read_text(encoding="utf-8")
    assert "from sqlalchemy.dialects.postgresql import insert as pg_insert" in source
