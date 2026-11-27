from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from openai import AsyncOpenAI

from config import OPENROUTER_API_KEY

router = Router()

_client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

MODELS = {
    "gpt":    ("openai/gpt-4o-mini",               "🟢 GPT-4o Mini"),
    "claude": ("anthropic/claude-haiku-4-5",        "🟣 Claude Haiku"),
    "grok":   ("x-ai/grok-4",                      "⚡ Grok 4"),
    "gemini": ("google/gemini-2.0-flash-001",       "🔷 Gemini Flash"),
}

DEFAULT_MODEL_KEY = "gpt"

# user_id -> model key
user_models: dict[int, str] = {}

SYSTEM_PROMPT = (
    "Ты полезный ассистент. Отвечай кратко и по делу. "
    "Если вопрос на русском — отвечай на русском."
)

WELCOME_TEXT = (
    "👋 Привет! Я твой AI-помощник.\n\n"
    "Я умею:\n"
    "• Отвечать на любые вопросы\n"
    "• Писать тексты, посты, письма\n"
    "• Разбирать и анализировать таблицы и данные\n"
    "• Переводить с любого языка\n"
    "• Объяснять сложные темы простым языком\n"
    "• Помогать с кодом и техническими задачами\n\n"
    "Команды:\n"
    "/model — выбрать модель AI\n\n"
    "Просто напиши мне что-нибудь! 🚀"
)


def _model_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"model:{key}")]
        for key, (_, label) in MODELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "/start — приветствие\n"
        "/model — выбрать модель AI\n"
        "/help — эта справка"
    )


@router.message(Command("model"))
async def cmd_model(message: Message) -> None:
    uid = message.from_user.id
    current_key = user_models.get(uid, DEFAULT_MODEL_KEY)
    _, current_label = MODELS[current_key]
    await message.answer(
        f"Текущая модель: {current_label}\nВыбери новую:",
        reply_markup=_model_keyboard(),
    )


@router.callback_query(F.data.startswith("model:"))
async def cb_model(callback: CallbackQuery) -> None:
    key = callback.data.split(":", 1)[1]
    if key not in MODELS:
        await callback.answer("Неизвестная модель", show_alert=True)
        return
    user_models[callback.from_user.id] = key
    _, label = MODELS[key]
    await callback.message.edit_text(f"Готово! Теперь отвечаю через {label}")
    await callback.answer()


@router.message()
async def handle_message(message: Message) -> None:
    user_text = message.text or message.caption
    if not user_text:
        await message.answer("Пришли текстовое сообщение — я отвечу на него.")
        return

    uid = message.from_user.id
    model_key = user_models.get(uid, DEFAULT_MODEL_KEY)
    model_id, model_label = MODELS[model_key]

    thinking = await message.answer("⏳ Думаю...")

    try:
        response = await _client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        )
        answer = response.choices[0].message.content or "Не получил ответ от модели."
    except Exception as e:
        answer = f"❌ Ошибка при запросе к {model_label}: {e}"

    await thinking.delete()
    await message.answer(answer)
