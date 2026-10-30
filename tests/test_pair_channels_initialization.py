import ast
from pathlib import Path

from sqlalchemy import inspect

from app.db.models import Pair


def test_new_pair_initializes_channels_collection():
    pair = Pair(
        user_id=1,
        pair_no=5,
        repost_style="random",
        movie_rule=False,
        is_active=True,
        is_paused=False,
        channels=[],
    )
    assert inspect(pair).attrs.channels.loaded_value == []


def test_repository_new_pair_constructor_initializes_channels():
    source = Path("app/db/repository.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    create_pair = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "create_pair"
    )
    pair_calls = [
        node
        for node in ast.walk(create_pair)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Pair"
    ]
    assert pair_calls, "Repository.create_pair must construct a Pair"
    assert any(
        any(keyword.arg == "channels" and isinstance(keyword.value, ast.List) and not keyword.value.elts
            for keyword in call.keywords)
        for call in pair_calls
    ), "New Pair objects must be constructed with channels=[] to avoid implicit async lazy loading"
