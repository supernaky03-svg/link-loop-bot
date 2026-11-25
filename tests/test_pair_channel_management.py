from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.bot.services.pair_channel_service as service
from app.db.models import Pair, PairChannel


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeRepo:
    def __init__(self, pair):
        self.pair = pair
        self.session = FakeSession()

    async def get_pair_by_no(self, user_id, pair_no):
        if self.pair.user_id == user_id and self.pair.pair_no == pair_no and self.pair.is_active:
            return self.pair
        return None


def make_pair(channels, *, paused=False, reason=None):
    pair = Pair(
        id=20,
        user_id=7,
        pair_no=3,
        is_active=True,
        is_paused=paused,
        paused_reason=reason,
        repost_style="by_order",
        channels=[],
    )
    pair.channels = channels
    for channel in channels:
        channel.pair_id = pair.id
    return pair


def make_channel(chat_id, order_no, *, active=True, admin_ok=True):
    return PairChannel(
        id=chat_id % 1000,
        pair_id=20,
        chat_id=chat_id,
        title=f"Channel {chat_id}",
        order_no=order_no,
        is_active=active,
        bot_admin_ok=admin_ok,
    )


@pytest.fixture
def fake_channel_resolution(monkeypatch):
    parsed = SimpleNamespace(raw="@added", order_no=1, error=None, missing=None)
    checked = SimpleNamespace(
        ok=True,
        chat_id=-100300,
        title="Added Channel",
        username="added",
        channel_link="https://t.me/added",
        invite_link=None,
        error=None,
    )
    monkeypatch.setattr(service, "_parse_single_channel", AsyncMock(return_value=parsed))
    monkeypatch.setattr(service, "_resolve_channel", AsyncMock(return_value=checked))


@pytest.mark.asyncio
async def test_add_channel_resumes_only_insufficient_channel_pause(monkeypatch, fake_channel_resolution):
    pair = make_pair([make_channel(-100100, 1)], paused=True, reason="insufficient_channels")
    repo = FakeRepo(pair)
    user = SimpleNamespace(id=7)
    monkeypatch.setattr(service, "user_limits", AsyncMock(return_value=(5, 4)))

    refreshed = await service.add_channel_to_pair(
        bot=object(), repo=repo, user=user, pair=pair, raw_channel="@added", settings=object()
    )

    assert refreshed is pair
    assert len([ch for ch in pair.channels if ch.is_active]) == 2
    assert pair.is_paused is False
    assert pair.paused_reason is None
    assert sorted(ch.order_no for ch in pair.channels if ch.is_active) == [1, 2]
    assert repo.session.commits == 1


@pytest.mark.asyncio
async def test_add_channel_rejects_duplicate_active_channel(monkeypatch, fake_channel_resolution):
    pair = make_pair([make_channel(-100300, 1), make_channel(-100100, 2)])
    repo = FakeRepo(pair)
    monkeypatch.setattr(service, "user_limits", AsyncMock(return_value=(5, 4)))

    with pytest.raises(service.ChannelManagementError, match="already active") as error:
        await service.add_channel_to_pair(object(), repo, SimpleNamespace(id=7), pair, "@added", object())

    assert error.value.status == 409
    assert repo.session.commits == 0


@pytest.mark.asyncio
async def test_add_channel_enforces_per_pair_user_limit(monkeypatch, fake_channel_resolution):
    pair = make_pair([make_channel(-100100, 1), make_channel(-100200, 2)])
    repo = FakeRepo(pair)
    monkeypatch.setattr(service, "user_limits", AsyncMock(return_value=(5, 2)))

    with pytest.raises(service.ChannelManagementError, match="Channel limit reached"):
        await service.add_channel_to_pair(object(), repo, SimpleNamespace(id=7), pair, "@added", object())

    assert len(pair.channels) == 2
    assert repo.session.commits == 0


@pytest.mark.asyncio
async def test_add_reactivates_soft_removed_channel_instead_of_creating_duplicate(monkeypatch, fake_channel_resolution):
    removed = make_channel(-100300, 1, active=False)
    pair = make_pair([make_channel(-100100, 1), removed])
    repo = FakeRepo(pair)
    monkeypatch.setattr(service, "user_limits", AsyncMock(return_value=(5, 4)))

    await service.add_channel_to_pair(object(), repo, SimpleNamespace(id=7), pair, "@added", object())

    assert len(pair.channels) == 2
    assert removed.is_active is True
    assert removed.title == "Added Channel"
    assert sum(ch.chat_id == -100300 for ch in pair.channels) == 1


@pytest.mark.asyncio
async def test_remove_soft_deactivates_and_pauses_when_fewer_than_two_remain():
    pair = make_pair([
        make_channel(-100100, 1),
        make_channel(-100200, 2),
        make_channel(-100300, 3),
    ])
    repo = FakeRepo(pair)
    user = SimpleNamespace(id=7)

    await service.remove_channel_from_pair(repo, user, pair, -100200)
    assert next(ch for ch in pair.channels if ch.chat_id == -100200).is_active is False
    assert len([ch for ch in pair.channels if ch.is_active]) == 2
    assert pair.is_paused is False
    assert sorted(ch.order_no for ch in pair.channels if ch.is_active) == [1, 2]

    await service.remove_channel_from_pair(repo, user, pair, -100300)
    assert len([ch for ch in pair.channels if ch.is_active]) == 1
    assert pair.is_paused is True
    assert pair.paused_reason == "insufficient_channels"


@pytest.mark.asyncio
async def test_remove_does_not_override_permission_pause_reason():
    pair = make_pair(
        [make_channel(-100100, 1, admin_ok=True), make_channel(-100200, 2, admin_ok=False), make_channel(-100300, 3)],
        paused=True,
        reason="bot_admin_missing",
    )
    repo = FakeRepo(pair)

    await service.remove_channel_from_pair(repo, SimpleNamespace(id=7), pair, -100300)

    assert pair.is_paused is True
    assert pair.paused_reason == "bot_admin_missing"


@pytest.mark.asyncio
async def test_remove_rejects_channel_not_active_in_selected_pair():
    pair = make_pair([make_channel(-100100, 1, active=False), make_channel(-100200, 2)])
    repo = FakeRepo(pair)

    with pytest.raises(service.ChannelManagementError, match="not active") as error:
        await service.remove_channel_from_pair(repo, SimpleNamespace(id=7), pair, -100100)

    assert error.value.status == 404
    assert repo.session.commits == 0

@pytest.mark.asyncio
async def test_add_can_resume_stale_admin_pause_after_broken_channel_was_removed(monkeypatch, fake_channel_resolution):
    pair = make_pair([make_channel(-100100, 1, admin_ok=True)], paused=True, reason="bot_admin_missing")
    repo = FakeRepo(pair)
    monkeypatch.setattr(service, "user_limits", AsyncMock(return_value=(5, 4)))

    await service.add_channel_to_pair(object(), repo, SimpleNamespace(id=7), pair, "@added", object())

    assert len([ch for ch in pair.channels if ch.is_active]) == 2
    assert pair.is_paused is False
    assert pair.paused_reason is None


@pytest.mark.asyncio
async def test_add_does_not_resume_if_an_existing_active_channel_still_lacks_admin(monkeypatch, fake_channel_resolution):
    pair = make_pair(
        [make_channel(-100100, 1, admin_ok=False)],
        paused=True,
        reason="insufficient_channels",
    )
    repo = FakeRepo(pair)
    monkeypatch.setattr(service, "user_limits", AsyncMock(return_value=(5, 4)))

    await service.add_channel_to_pair(object(), repo, SimpleNamespace(id=7), pair, "@added", object())

    assert len([ch for ch in pair.channels if ch.is_active]) == 2
    assert pair.is_paused is True
    assert pair.paused_reason == "insufficient_channels"


@pytest.mark.asyncio
async def test_remove_preserves_unrelated_manual_pause_reason_when_pair_becomes_undersized():
    pair = make_pair(
        [make_channel(-100100, 1), make_channel(-100200, 2)],
        paused=True,
        reason="manual_admin_pause",
    )
    repo = FakeRepo(pair)

    await service.remove_channel_from_pair(repo, SimpleNamespace(id=7), pair, -100200)

    assert len([ch for ch in pair.channels if ch.is_active]) == 1
    assert pair.is_paused is True
    assert pair.paused_reason == "manual_admin_pause"
