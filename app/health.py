from __future__ import annotations

from aiohttp import web

from app.config import Settings
from app.webapp import create_web_app


async def start_health_server(settings: Settings, bot) -> web.AppRunner:
    app = create_web_app(settings, bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.health_host, settings.port)
    await site.start()
    return runner
