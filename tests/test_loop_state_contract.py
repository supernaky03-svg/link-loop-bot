import asyncio

from sqlalchemy.exc import IntegrityError

from app.db.models import LoopState
from app.db.repository import Repository


def test_loop_state_has_one_origin_claim_per_pair():
    constraints = {
        c.name: tuple(col.name for col in c.columns)
        for c in LoopState.__table__.constraints
        if c.name
    }
    assert constraints['uq_loop_origin'] == ('pair_id', 'origin_chat_id', 'origin_message_id')


def test_second_claim_for_same_origin_returns_existing_loop():
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeSession:
        def __init__(self):
            self.added = []
            self.commits = 0
            self.existing = None

        def add(self, value):
            self.added.append(value)

        async def commit(self):
            self.commits += 1
            if self.commits == 2:
                raise IntegrityError('insert', {}, Exception('unique violation'))

        async def rollback(self):
            return None

        async def execute(self, statement):
            return Result(self.existing)

    async def scenario():
        session = FakeSession()
        repo = Repository(session)
        first = await repo.create_loop_state('loop-a', 1, -100, 10, [-100, -200], [7])
        assert first.loop_id == 'loop-a'
        session.existing = first
        second = await repo.create_loop_state('loop-b', 1, -100, 10, [-100, -200], [7])
        assert second.loop_id == 'loop-a'

    asyncio.run(scenario())
