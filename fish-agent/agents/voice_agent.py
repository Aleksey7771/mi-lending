"""
VoiceAgent: transcribes Telegram voice messages via OpenAI Whisper.
"""
import logging
import tempfile
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.openai_api_key)


async def transcribe(voice_bytes: bytes, file_ext: str = "ogg") -> str | None:
    """
    Send audio bytes to OpenAI Whisper, get Russian text back.
    Returns transcribed text or None on failure.
    """
    if not is_configured():
        return None

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Write to temp file — Whisper API requires a file object
        with tempfile.NamedTemporaryFile(suffix=f".{file_ext}", delete=False) as tmp:
            tmp.write(voice_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as audio_file:
                result = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru",
                    response_format="text",
                )
            text = result.strip() if isinstance(result, str) else str(result).strip()
            logger.info("Whisper: '%s'", text[:80])
            return text
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error("Whisper transcription failed: %s", e)
        return None
