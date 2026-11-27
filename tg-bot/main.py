import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import catalog, common, content, kp, price, style
from middleware.owner import OwnerOnlyMiddleware


logging.basicConfig(level=logging.INFO)


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Security: only ALLOWED_USER_ID can interact with this bot
    dp.message.middleware(OwnerOnlyMiddleware())

    dp.include_router(catalog.router)
    dp.include_router(content.router)
    dp.include_router(price.router)
    dp.include_router(kp.router)
    dp.include_router(style.router)
    dp.include_router(common.router)  # catchall last

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
