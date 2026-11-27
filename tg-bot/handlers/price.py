import json
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
from openai import AsyncOpenAI

import config
from ai.transcriber import transcribe_voice
from db.catalog import find_product_fuzzy, get_public_catalog, update_product
from db.database import get_db
from platforms import max_content, telegram_channel

logger = logging.getLogger(__name__)

_ai_client = AsyncOpenAI(
    api_key=config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

router = Router()


class PriceStates(StatesGroup):
    waiting_confirmation = State()
    waiting_correction = State()


def format_price_list(products: list[dict]) -> str:
    if not products:
        return "Каталог пуст — нет товаров в наличии."

    by_category: dict[str, list[dict]] = {}
    for p in products:
        cat = p.get("category", "другое")
        by_category.setdefault(cat, []).append(p)

    lines = ["<b>Актуальный прайс-лист:</b>\n"]
    for category, items in by_category.items():
        lines.append(f"\n<b>{category.upper()}</b>")
        for p in items:
            origin = p.get("origin", "")
            origin_str = f" ({origin})" if origin else ""
            retail = p.get("price_retail")
            wholesale = p.get("price_wholesale")
            unit = p.get("unit", "кг")
            retail_str = f"{retail:,.0f} ₽/{unit}" if retail else "—"
            wholesale_str = f"{wholesale:,.0f} ₽/{unit}" if wholesale else "—"
            lines.append(
                f"  {p['name']}{origin_str} — "
                f"опт: {wholesale_str} | розница: {retail_str}"
            )
    return "\n".join(lines)


async def _ai_parse_price_update(text: str) -> dict | None:
    """Извлекает из текста: товар, тип цены, значение. Возвращает dict или None."""
    prompt = (
        "Из текста извлеки исправление цены для прайс-листа оптовой торговли морепродуктами.\n"
        f'Текст: "{text}"\n\n'
        "Ответь ТОЛЬКО JSON без пояснений:\n"
        '{"product": "название товара", "type": "опт"|"розница", "value": число}\n\n'
        "Правила:\n"
        "- product: только название товара (например: горбуша, икра горбуши, кета)\n"
        "- type: «опт» если оптовая цена, «розница» если розничная; "
        "если не указано — «опт»\n"
        "- value: только число (без рублей)\n"
        "Если не удаётся извлечь — ответь: null"
    )
    try:
        response = await _ai_client.chat.completions.create(
            model=config.ROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=80,
        )
        raw = response.choices[0].message.content.strip()
        if raw.lower() == "null":
            return None
        # strip markdown code fences if present
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        data = json.loads(raw)
        field = "price_retail" if data.get("type") == "розница" else "price_wholesale"
        return {
            "product": str(data.get("product", "")).strip(),
            "field": field,
            "value": float(data["value"]),
        }
    except Exception as e:
        logger.warning("AI price parse failed: %s", e)
        return None


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Публикуем", callback_data="price_confirm"),
            InlineKeyboardButton(text="✏️ Исправлю цену", callback_data="price_edit"),
        ],
    ])


@router.message(Command("price"))
async def cmd_price(message: Message, state: FSMContext) -> None:
    async with get_db() as db:
        products = await get_public_catalog(db)

    text = format_price_list(products)
    await state.update_data(price_products=products)
    await state.set_state(PriceStates.waiting_confirmation)
    await message.answer(text + "\n\nЦены актуальны? Публикуем?",
                         reply_markup=_confirm_keyboard())


@router.callback_query(F.data == "price_confirm")
async def handle_price_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    products = data.get("price_products", [])
    price_text = format_price_list(products)

    bot = callback.bot
    tg_ok = await telegram_channel.publish_post(bot, price_text, photo_file_id=None)
    max_ok = await max_content.publish_post(price_text, photo_url=None)

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)

    parts = []
    if tg_ok:
        parts.append("Telegram")
    if max_ok:
        parts.append("Max")

    channels = " + ".join(parts) if parts else "нигде (ошибка публикации)"
    await callback.message.answer(f"✅ Прайс опубликован ({channels}).")
    await callback.answer()


@router.callback_query(F.data == "price_edit")
async def handle_price_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PriceStates.waiting_correction)
    await callback.message.answer(
        "Напишите или скажите голосом исправление, например: «горбуша на 480»"
    )
    await callback.answer()


@router.message(PriceStates.waiting_correction)
async def handle_price_correction(message: Message, state: FSMContext) -> None:
    if message.voice:
        await message.answer("🎤 Распознаю...")
        try:
            text = await transcribe_voice(message.bot, message.voice)
        except Exception:
            await message.answer("⚠️ Не удалось распознать голос. Попробуйте ещё раз.")
            return
        if not text:
            await message.answer("Ничего не распознано. Скажите чётче.")
            return
        await message.answer(f"🗣 «{text}»")
    else:
        text = (message.text or "").strip()

    parsed = await _ai_parse_price_update(text)
    if parsed is None:
        await message.answer(
            "Не понял. Скажите или напишите, например:\n"
            "«горбуша опт 240» или «икра горбуши розница 3500»"
        )
        return

    name_raw = parsed["product"]
    price_field = parsed["field"]
    price_val = parsed["value"]
    price_label = "розница" if price_field == "price_retail" else "опт"

    async with get_db() as db:
        product = await find_product_fuzzy(db, name_raw)
        if product is None:
            await message.answer(
                f"Товар «{name_raw}» не найден в каталоге. "
                "Проверьте название командой /catalog."
            )
            return
        await update_product(db, product["name"], **{price_field: price_val})
        products = await get_public_catalog(db)

    await state.update_data(price_products=products)
    await state.set_state(PriceStates.waiting_confirmation)
    text_updated = format_price_list(products)
    await message.answer(
        f"✅ {product['name']}: {price_label} → {price_val:,.0f} ₽\n\n"
        + text_updated + "\n\nЦены актуальны? Публикуем?",
        reply_markup=_confirm_keyboard(),
    )
