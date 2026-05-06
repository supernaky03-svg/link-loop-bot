from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from app.bot.handlers import register_handlers
from app.bot.loader import create_bot, create_dispatcher
from app.config import get_settings
from app.db.session import close_db, init_db
from app.health import start_health_server


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    )
    logger = logging.getLogger(__name__)

    await init_db()
    bot = create_bot(settings)
    dp = create_dispatcher(settings)
    register_handlers(dp)
    health_runner = await start_health_server(settings)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    polling_task = asyncio.create_task(dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()))
    logger.info('Bot started. Health endpoint: %s:%s%s', settings.health_host, settings.port, settings.health_path)

    await stop_event.wait()
    logger.info('Stopping bot...')
    polling_task.cancel()
    with suppress(asyncio.CancelledError):
        await polling_task
    await health_runner.cleanup()
    await bot.session.close()
    await close_db()


if __name__ == '__main__':
    asyncio.run(main())
