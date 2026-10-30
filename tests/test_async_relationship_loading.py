from app.db.models import User


def test_user_pairs_uses_selectin_loading_for_async_sessions():
    assert User.pairs.property.lazy == "selectin"
