from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace_method(source: str, name: str, replacement: str) -> str:
    marker = f"    async def {name}("
    start = source.find(marker)
    if start < 0:
        raise RuntimeError(f"Could not find Repository.{name}()")
    next_async = source.find("\n    async def ", start + len(marker))
    next_sync = source.find("\n    def ", start + len(marker))
    candidates = [pos for pos in (next_async, next_sync) if pos >= 0]
    end = min(candidates) if candidates else len(source)
    # Preserve the class indentation and replace exactly one complete method.
    return source[:start] + replacement.rstrip() + "\n" + source[end:]


def main() -> None:
    path = ROOT / "app/db/repository.py"
    if not path.exists():
        raise SystemExit("app/db/repository.py is missing; run this from the repository root.")

    source = path.read_text(encoding="utf-8")
    if "from sqlalchemy.dialects.postgresql import insert as pg_insert" not in source:
        anchor = "from sqlalchemy.exc import IntegrityError\n"
        if source.count(anchor) != 1:
            raise RuntimeError("Could not locate SQLAlchemy IntegrityError import; source version mismatch.")
        source = source.replace(
            anchor,
            anchor + "from sqlalchemy.dialects.postgresql import insert as pg_insert\n",
            1,
        )

    mark_processed = '''    async def mark_processed(self, pair_id: int, chat_id: int, message_id: int) -> bool:
        """Atomically claim an update without rolling back the surrounding session.

        A normal IntegrityError + session.rollback() expires every loaded ORM object
        in this AsyncSession, including Pair objects held by channel_posts.py. The
        next attribute read can then attempt implicit async IO and raise MissingGreenlet.
        PostgreSQL ON CONFLICT keeps duplicate delivery idempotent without that side effect.
        """
        statement = (
            pg_insert(ProcessedUpdate)
            .values(pair_id=pair_id, chat_id=chat_id, message_id=message_id)
            .on_conflict_do_nothing(
                index_elements=[
                    ProcessedUpdate.pair_id,
                    ProcessedUpdate.chat_id,
                    ProcessedUpdate.message_id,
                ]
            )
            .returning(ProcessedUpdate.id)
        )
        result = await self.session.execute(statement)
        inserted_id = result.scalar_one_or_none()
        await self.session.commit()
        return inserted_id is not None
'''

    create_loop_state = '''    async def create_loop_state(
        self,
        loop_id: str,
        pair_id: int,
        origin_chat_id: int,
        origin_message_id: int,
        route_chat_ids: list[int],
        selected_unit_ids: list[int] | None = None,
    ) -> LoopState | None:
        """Claim a loop origin atomically without session-wide rollback on duplicates."""
        statement = (
            pg_insert(LoopState)
            .values(
                loop_id=loop_id,
                pair_id=pair_id,
                origin_chat_id=origin_chat_id,
                origin_message_id=origin_message_id,
                route_chat_ids=route_chat_ids,
                selected_unit_ids=selected_unit_ids or [],
                created_message_ids={},
                footer_message_ids={},
                current_index=0,
                status='running',
            )
            .on_conflict_do_nothing(
                index_elements=[
                    LoopState.pair_id,
                    LoopState.origin_chat_id,
                    LoopState.origin_message_id,
                ]
            )
            .returning(LoopState.id)
        )
        result = await self.session.execute(statement)
        inserted_id = result.scalar_one_or_none()
        await self.session.commit()

        if inserted_id is not None:
            return await self.get_loop_state(loop_id)

        existing_result = await self.session.execute(
            select(LoopState).where(
                LoopState.pair_id == pair_id,
                LoopState.origin_chat_id == origin_chat_id,
                LoopState.origin_message_id == origin_message_id,
            )
        )
        logger.info(
            'loop already claimed for origin',
            extra={'pair_id': pair_id, 'chat_id': origin_chat_id, 'message_id': origin_message_id},
        )
        return existing_result.scalar_one_or_none()
'''

    save_loop_event = '''    async def save_loop_event(
        self,
        loop_id: str,
        pair_id: int,
        origin_chat_id: int,
        origin_message_id: int,
        from_chat_id: int,
        from_message_id: int,
        to_chat_id: int,
        to_message_id: int,
        status: str = 'sent',
    ) -> None:
        """Persist a bot-created message idempotently without expiring loaded objects."""
        statement = (
            pg_insert(LoopEvent)
            .values(
                loop_id=loop_id,
                pair_id=pair_id,
                origin_chat_id=origin_chat_id,
                origin_message_id=origin_message_id,
                from_chat_id=from_chat_id,
                from_message_id=from_message_id,
                to_chat_id=to_chat_id,
                to_message_id=to_message_id,
                created_by_bot=True,
                status=status,
            )
            # Both event uniqueness guards represent duplicate delivery, so ignore
            # either conflict. Do not IntegrityError/rollback the shared AsyncSession.
            .on_conflict_do_nothing()
        )
        await self.session.execute(statement)
        await self.session.commit()
'''

    source = replace_method(source, "mark_processed", mark_processed)
    source = replace_method(source, "create_loop_state", create_loop_state)
    source = replace_method(source, "save_loop_event", save_loop_event)

    if "await self.session.rollback()" in source:
        # Other methods (e.g. PostUnit's cache-insert race) can still use rollback.
        # They run before Pair objects are loaded in channel_posts and are intentionally
        # not changed here. The three writes used during pair fan-out must be clean.
        pass

    path.write_text(source, encoding="utf-8")
    print("Applied PostgreSQL ON CONFLICT dedupe fix to mark_processed, create_loop_state, and save_loop_event.")


if __name__ == "__main__":
    main()
