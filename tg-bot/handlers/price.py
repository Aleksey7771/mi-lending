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

from db.catalog import get_public_catalog, update_product
from db.database import get_db
from platforms import max_content, telegram_channel

logger = logging.getLogger(__name__)

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
                f"розница: {retail_str} | опт: {wholesale_str}"
            )
    return "\n".join(lines)


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
    await state.update({"price_products": products})
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
        "Напишите исправление, например: «горбуша на 480»"
    )
    await callback.answer()


@router.message(PriceStates.waiting_correction)
async def handle_price_correction(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    # Parse "горбуша на 480" or "икру на 2900"
    m = re.search(r"(.+?)\s+на\s+(\d+(?:[.,]\d+)?)", text.lower())
    if not m:
        await message.answer(
            "Не понял. Напишите в формате «горбуша на 480»."
        )
        return

    name_raw = m.group(1).strip()
    price_val = float(m.group(2).replace(",", "."))

    async with get_db() as db:
        updated = await update_product(db, name_raw.capitalize(),
                                       price_wholesale=price_val)
        if not updated:
            await message.answer(
                f"Товар «{name_raw}» не найден в каталоге."
            )
            return
        products = await get_public_catalog(db)

    await state.update({"price_products": products})
    await state.set_state(PriceStates.waiting_confirmation)
    text_updated = format_price_list(products)
    await message.answer(
        text_updated + "\n\nЦены актуальны? Публикуем?",
        reply_markup=_confirm_keyboard(),
    )
