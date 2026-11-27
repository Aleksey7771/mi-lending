import re
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from ai.generator import generate_post
from ai.router import detect_intent
from db.catalog import get_all_products, get_product, find_product_fuzzy
from db.catalog import get_public_catalog
from handlers.price import format_price_list, PriceStates, _confirm_keyboard
from db.database import get_db
from db.style import get_style_profile
from platforms import max_content, telegram_channel

logger = logging.getLogger(__name__)

router = Router()


class ContentStates(StatesGroup):
    waiting_approval = State()


def _extract_product_name(text: str) -> str | None:
    patterns = [
        r"пост про (.+)",
        r"пост о (.+)",
        r"напиши про (.+)",
        r"пост для (.+)",
        r"про (.+)",
    ]
    for pat in patterns:
        m = re.search(pat, text.lower())
        if m:
            name = m.group(1).strip().rstrip(".,!?")
            return name.capitalize()
    words = text.split()
    nouns = [w for w in words if len(w) > 3 and w.lower() not in
             ("напиши", "пост", "сделай", "создай", "отправь")]
    return nouns[0].capitalize() if nouns else None


def _preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data="publish_post"),
            InlineKeyboardButton(text="🔄 Переписать", callback_data="rewrite_post"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_post"),
        ],
    ])


async def process_text_command(message: Message, state: FSMContext, text: str) -> None:
    intent = await detect_intent(text)

    if intent == "POST":
        name = _extract_product_name(text)
        if not name:
            await message.answer("Укажите название товара из каталога.")
            return

        async with get_db() as db:
            product = await find_product_fuzzy(db, name)

        if product is None:
            await message.answer(
                f"Товар «{name}» не найден в каталоге. "
                "Проверьте название командой /catalog."
            )
            return

        try:
            async with get_db() as style_db:
                style = await get_style_profile(style_db)
            post_text = await generate_post(product, text, style_profile=style)
        except Exception as e:
            logger.error("generate_post failed: %s", e)
            await message.answer("Ошибка генерации поста. Попробуйте ещё раз.")
            return

        await state.update_data(post_text=post_text, product=product)
        await state.set_state(ContentStates.waiting_approval)

        preview = f"<b>Превью поста:</b>\n\n{post_text}"
        await message.answer(preview, reply_markup=_preview_keyboard())

    elif intent == "CATALOG_VIEW":
        async with get_db() as db:
            products = await get_all_products(db, in_stock_only=False)
        if not products:
            await message.answer("Каталог пуст. Добавьте товары командой /catalog")
            return
        lines = ["<b>Каталог товаров</b>\n"]
        cur_cat = None
        for p in products:
            if p["category"] != cur_cat:
                cur_cat = p["category"]
                lines.append(f"\n<b>{cur_cat.upper()}</b>")
            icon = "✅" if p["in_stock"] else "❌"
            lines.append(f"{icon} {p['name']} — опт: {p['price_wholesale']} ₽")
        await message.answer("\n".join(lines))

    elif intent in ("CATALOG_ADD", "CATALOG_UPDATE"):
        name = _extract_product_name(text)
        if name:
            async with get_db() as db:
                product = await get_product(db, name)
            if product is None:
                await message.answer(
                    f"Товар «{name}» не найден в каталоге. "
                    "Проверьте название командой /catalog."
                )
                return
        await message.answer(
            "Управление каталогом — команда /catalog\n"
            "Редактирование через кнопки в каталоге."
        )

    elif intent == "PRICE":
        async with get_db() as db:
            products = await get_public_catalog(db)
        text = format_price_list(products)
        await state.update_data(price_products=products)
        await state.set_state(PriceStates.waiting_confirmation)
        await message.answer(text + "\n\nЦены актуальны? Публикуем?",
                             reply_markup=_confirm_keyboard())

    else:
        await message.answer(
            "Не понял команду. Что хотите сделать?\n\n"
            "📝 <b>Пост</b> — «напиши пост про горбушу»\n"
            "💰 <b>Прайс</b> — «прайс» или «покажи цены»\n"
            "📄 <b>КП</b> — «сделай КП на краба»\n"
            "📦 <b>Каталог</b> — «что у нас есть»"
        )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: Message, state: FSMContext) -> None:
    await process_text_command(message, state, message.text or "")


@router.callback_query(F.data == "publish_post")
async def handle_publish_post(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    post_text = data.get("post_text", "")
    product = data.get("product", {})
    photo_file_id = product.get("photo_file_id") if product else None

    bot = callback.bot
    tg_ok = await telegram_channel.publish_post(bot, post_text, photo_file_id)
    max_ok = await max_content.publish_post(post_text, photo_url=None)

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)

    parts = []
    if tg_ok:
        parts.append("Telegram")
    if max_ok:
        parts.append("Max")

    if parts:
        channels = " + ".join(parts)
        await callback.message.answer(
            f"✅ Опубликовано ({channels}). Как вышло?\n"
            "👍 Хорошо  |  ✏️ Слишком длинно"
        )
    else:
        await callback.message.answer(
            "⚠️ Не удалось опубликовать. Текст сохранён:\n\n" + post_text
        )
    await callback.answer()


@router.callback_query(F.data == "cancel_post")
async def handle_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отменено.")


@router.callback_query(F.data == "rewrite_post")
async def handle_rewrite(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    product = data.get("product")
    if not product:
        await callback.answer("Нет данных для перезаписи.")
        return

    try:
        post_text = await generate_post(product, "перепиши пост", style_profile=None)
    except Exception as e:
        logger.error("rewrite failed: %s", e)
        await callback.answer("Ошибка генерации. Попробуйте ещё раз.")
        return

    await state.update_data(post_text=post_text)
    preview = f"<b>Превью поста (новый вариант):</b>\n\n{post_text}"
    await callback.message.edit_text(preview, reply_markup=_preview_keyboard())
    await callback.answer()
