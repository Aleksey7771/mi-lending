from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db.catalog import (
    add_product,
    get_all_products,
    get_product,
    set_stock,
    update_product,
)
from db.database import get_db

router = Router()


@router.message(Command("catalog"))
async def cmd_catalog(message: Message) -> None:
    async with get_db() as db:
        products = await get_all_products(db, in_stock_only=False)

    if not products:
        await message.answer("Каталог пуст. Добавьте товары командой /add_product")
        return

    lines = ["<b>Каталог товаров</b>\n"]
    current_category = None
    for p in products:
        if p["category"] != current_category:
            current_category = p["category"]
            lines.append(f"\n<b>{current_category.upper()}</b>")
        stock_icon = "✅" if p["in_stock"] else "❌"
        lines.append(
            f"{stock_icon} {p['name']} — розница: {p['price_retail']} ₽, "
            f"опт: {p['price_wholesale']} ₽"
        )

    await message.answer("\n".join(lines))
