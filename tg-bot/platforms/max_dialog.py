import logging

import httpx

import config

logger = logging.getLogger(__name__)
_MAX_API_BASE = "https://botapi.max.ru"


def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient()


async def get_updates(offset: int = 0) -> list[dict]:
    url = (
        f"{_MAX_API_BASE}/updates"
        f"?access_token={config.MAX_DIALOG_BOT_TOKEN}"
        f"&offset={offset}&limit=100&timeout=5"
    )
    try:
        async with _get_client() as client:
            resp = await client.get(url, timeout=10)
        if resp.status_code != 200:
            logger.error("Max dialog get_updates %s: %s", resp.status_code, resp.text)
            return []
        return resp.json().get("updates", [])
    except Exception as e:
        logger.error("Max dialog get_updates failed: %s", e)
        return []


async def send_message(chat_id: str, text: str) -> bool:
    url = f"{_MAX_API_BASE}/messages?access_token={config.MAX_DIALOG_BOT_TOKEN}"
    payload = {"recipient": {"chat_id": chat_id}, "type": "text", "text": text}
    try:
        async with _get_client() as client:
            resp = await client.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error("Max dialog send_message %s: %s", resp.status_code, resp.text)
            return False
        return True
    except Exception as e:
        logger.error("Max dialog send_message failed: %s", e)
        return False
