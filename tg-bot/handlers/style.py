from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from db.catalog import get_all_products
from db.database import get_db
from db.style import DEFAULT_PROFILE, add_feedback, save_style_profile

router = Router()

_STYLE_OPTIONS = {
    "А": {
        "label": "А — деловой",
        "tone": "professional",
        "emoji_density": "none",
        "length": "short",
        "cta_style": "soft",
        "example": "Горбуша б/г. Камчатка. 185₽/кг опт. В наличии. @manager",
    },
    "Б": {
        "label": "Б — личный",
        "tone": "casual",
        "emoji_density": "medium",
        "length": "medium",
        "cta_style": "soft",
        "example": (
            "Только что привезли горбушу с Камчатки 🎣\n"
            "Вылов этой недели, жирная — сезон! 185₽/кг от 5 кг.\n"
            "Пишите в личку."
        ),
    },
    "В": {
        "label": "В — профессиональный с эмоцией",
        "tone": "mixed",
        "emoji_density": "low",
        "length": "medium",
        "cta_style": "soft",
        "example": (
            "🐟 Горбуша б/г | Камчатка\n"
            "📦 Свежий вылов, вес блока 22 кг\n"
            "💰 Опт от 5 кг — 185 ₽/кг\n"
            "Звоните или пишите: @manager"
        ),
    },
}


def _style_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=opt["label"], callback_data=f"style_{key}")]
        for key, opt in _STYLE_OPTIONS.items()
    ])


@router.message(Command("style"))
async def cmd_style(message: Message) -> None:
    lines = ["<b>Выберите стиль текстов:</b>\n"]
    for key, opt in _STYLE_OPTIONS.items():
        lines.append(f"<b>{opt['label']}:</b>")
        lines.append(f"<i>{opt['example']}</i>\n")

    await message.answer("\n".join(lines), reply_markup=_style_keyboard())


@router.callback_query(F.data.startswith("style_"))
async def handle_style_choice(callback: CallbackQuery) -> None:
    key = callback.data.replace("style_", "")
    opt = _STYLE_OPTIONS.get(key)
    if not opt:
        await callback.answer("Неизвестный стиль.")
        return

    profile = {
        **DEFAULT_PROFILE,
        "tone": opt["tone"],
        "emoji_density": opt["emoji_density"],
        "length": opt["length"],
        "cta_style": opt["cta_style"],
    }
    async with get_db() as db:
        await save_style_profile(db, profile)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✅ Стиль «{opt['label']}» сохранён! Теперь пишу в этом стиле."
    )
    await callback.answer()


@router.message(Command("feedback"))
async def cmd_feedback(message: Message) -> None:
    await message.answer(
        "Оцените последний пост:\n"
        "👍 — хорошо\n"
        "✏️ — слишком длинно / коротко / официально / неформально\n\n"
        "Нажмите кнопку или напишите свой комментарий."
    )


@router.callback_query(F.data.startswith("feedback_"))
async def handle_feedback(callback: CallbackQuery) -> None:
    rating = callback.data.replace("feedback_", "")
    async with get_db() as db:
        await add_feedback(db, "", "post", rating)
    await callback.answer("Спасибо! Учту в следующем посте.")
