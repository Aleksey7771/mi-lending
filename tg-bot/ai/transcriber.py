import os
import tempfile
import logging

from openai import AsyncOpenAI

import config

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(
    api_key=config.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


async def transcribe_voice(bot, voice) -> str:
    """Download voice from Telegram and transcribe with Groq Whisper."""
    file_info = await bot.get_file(voice.file_id)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".ogg")
    os.close(tmp_fd)
    try:
        await bot.download_file(file_info.file_path, tmp_path)
        with open(tmp_path, "rb") as audio_file:
            transcript = await _client.audio.transcriptions.create(
                model=config.WHISPER_MODEL,
                file=audio_file,
                language="ru",
            )
        return transcript.text.strip()
    except Exception as e:
        logger.error("Voice transcription failed: %s", e)
        raise
    finally:
        os.unlink(tmp_path)
