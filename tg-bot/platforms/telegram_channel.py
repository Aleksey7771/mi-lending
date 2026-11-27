import logging

import config

logger = logging.getLogger(__name__)


async def publish_post(bot, text: str, photo_file_id: str | None) -> bool:
    try:
        if photo_file_id:
            await bot.send_photo(
                config.TELEGRAM_CHANNEL_ID,
                photo=photo_file_id,
                caption=text,
            )
        else:
            await bot.send_message(
                config.TELEGRAM_CHANNEL_ID,
                text=text,
            )
        return True
    except Exception as e:
        logger.error("Telegram publish failed: %s", e)
        return False
