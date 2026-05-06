from __future__ import annotations

from aiohttp import web

from app.config import Settings


async def ok(_request: web.Request) -> web.Response:
    return web.json_response({'ok': True})


async def start_health_server(settings: Settings) -> web.AppRunner:
    app = web.Application()
    app.router.add_route('*', settings.health_path, ok)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.health_host, settings.port)
    await site.start()
    return runner
