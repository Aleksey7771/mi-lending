import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import catalog, common, content, dialog_notification, kp, price, style, voice
from middleware.owner import OwnerOnlyMiddleware
from polling.max_dialog_loop import run_max_dialog_loop


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
    dp.include_router(dialog_notification.router)
    dp.include_router(voice.router)
    dp.include_router(common.router)  # catchall last

    asyncio.create_task(run_max_dialog_loop(bot))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
