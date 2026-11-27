import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ai.transcriber import transcribe_voice
from handlers.content import process_text_command

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.voice)
async def handle_voice_message(message: Message, state: FSMContext) -> None:
    await message.answer("🎤 Распознаю...")
    try:
        text = await transcribe_voice(message.bot, message.voice)
    except Exception:
        await message.answer("⚠️ Не удалось распознать голос. Попробуйте ещё раз.")
        return

    if not text:
        await message.answer("Ничего не распознано. Говорите чётче.")
        return

    await message.answer(f"🗣 «{text}»")
    await process_text_command(message, state, text)
