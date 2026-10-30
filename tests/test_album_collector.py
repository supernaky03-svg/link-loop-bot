import asyncio
import sys
import types

# album_service imports Message only for typing. Stub aiogram so this focused test
# can run in the offline build environment without installing Telegram libraries.
aiogram = types.ModuleType('aiogram')
aiogram_types = types.ModuleType('aiogram.types')
aiogram_types.Message = object
sys.modules.setdefault('aiogram', aiogram)
sys.modules.setdefault('aiogram.types', aiogram_types)

from app.bot.services.album_service import AlbumCollector


class Chat:
    def __init__(self, chat_id):
        self.id = chat_id


class Msg:
    def __init__(self, message_id, group='album-1'):
        self.message_id = message_id
        self.media_group_id = group
        self.chat = Chat(-100)


def test_album_timer_is_reset_by_new_messages():
    async def scenario():
        collector = AlbumCollector(0.05)
        received = []

        async def cb(messages):
            received.append([m.message_id for m in messages])

        await collector.add(Msg(1), cb)
        await asyncio.sleep(0.03)
        await collector.add(Msg(2), cb)
        await asyncio.sleep(0.03)
        assert received == []
        await asyncio.sleep(0.08)
        assert received == [[1, 2]]

    asyncio.run(scenario())


def test_ten_message_album_flushes_without_extra_delay():
    async def scenario():
        collector = AlbumCollector(1.0)
        received = []

        async def cb(messages):
            received.append([m.message_id for m in messages])

        for i in range(1, 11):
            await collector.add(Msg(i), cb)
        assert received == [[i for i in range(1, 11)]]

    asyncio.run(scenario())
