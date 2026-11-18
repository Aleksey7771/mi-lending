import asyncio
import logging
import os
import sys

# GTK3 для WeasyPrint на Windows (на Linux не нужно)
if sys.platform == "win32":
    _gtk = r"C:\Program Files\GTK3-Runtime Win64\bin"
    if os.path.isdir(_gtk) and _gtk not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _gtk + os.pathsep + os.environ.get("PATH", "")

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import callbacks, commands, text
from bot.middleware import WhitelistMiddleware
from config import settings
from memory.db import engine
from memory.models import Base
from memory.redis_client import close_redis, get_redis
from scheduler.jobs import setup_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB tables ensured.")

    redis = get_redis()
    await redis.ping()
    logger.info("Redis OK.")


async def on_shutdown(bot: Bot) -> None:
    await close_redis()
    await engine.dispose()


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def run_health_server() -> None:
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Health server started on :8080")


async def main() -> None:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.update.middleware(WhitelistMiddleware())

    dp.include_router(commands.router)
    dp.include_router(callbacks.router)
    dp.include_router(text.router)  # must be last — catches all messages

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await run_health_server()

    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started.")

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
