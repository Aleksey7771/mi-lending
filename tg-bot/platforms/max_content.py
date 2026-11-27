import logging

import httpx

import config

logger = logging.getLogger(__name__)

_MAX_API_BASE = "https://botapi.max.ru"


async def publish_post(text: str, photo_url: str | None) -> bool:
    url = f"{_MAX_API_BASE}/messages?access_token={config.MAX_CONTENT_BOT_TOKEN}"
    payload: dict = {
        "recipient": {"chat_id": config.MAX_CONTENT_CHANNEL_ID},
        "type": "text",
        "text": text,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error("Max API returned %s: %s", resp.status_code, resp.text)
            return False
        return True
    except Exception as e:
        logger.error("Max publish failed: %s", e)
        return False
