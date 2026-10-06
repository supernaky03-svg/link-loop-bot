# Files in this overlay

Changed runtime files:
- `app/config.py`
- `app/main.py`
- `app/db/base.py`
- `app/db/models.py`
- `app/db/repository.py`
- `app/db/session.py`
- `app/bot/handlers/channel_posts.py`
- `app/bot/services/album_service.py`
- `app/bot/services/link_service.py`
- `app/bot/services/movie_rule_service.py`
- `app/bot/services/repost_service.py`

Regression tests:
- `tests/test_loop_state_contract.py`
- `tests/test_link_entity_preservation.py`
- `tests/test_album_collector.py`

Empty `__init__.py` files are included where needed for the standalone test workspace.
