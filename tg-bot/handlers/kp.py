import logging
import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

import config
from db.catalog import get_product
from db.database import get_db
from pdf.kp_generator import generate_kp_pdf

logger = logging.getLogger(__name__)

router = Router()


def _parse_kp_command(text: str) -> tuple[str, list[str]]:
    """Extract client name and product names from command text.

    Example: "КП для ресторана Якорь: горбуша, икра горбуши"
    Returns: ("ресторан Якорь", ["горбуша", "икра горбуши"])
    """
    text = text.strip()
    # Remove /kp prefix if present
    text = re.sub(r"^/kp\s*", "", text, flags=re.IGNORECASE).strip()

    # Try "для <client>: <products>" or "для <client> — <products>"
    m = re.match(r"(?:для\s+)?(.+?)[\s:—-]+(.+)", text, re.IGNORECASE)
    if m:
        client = m.group(1).strip()
        products_raw = m.group(2)
        products = [p.strip().capitalize() for p in re.split(r"[,;]+", products_raw) if p.strip()]
        return client, products

    # Fallback: treat whole text as client name, no products
    return text or "Клиент", []


@router.message(Command("kp"))
async def cmd_kp(message: Message) -> None:
    text = message.text or ""
    client_name, product_names = _parse_kp_command(text)

    if not product_names:
        await message.answer(
            "Укажите клиента и товары. Например:\n"
            "<code>/kp ресторан Якорь: горбуша, икра горбуши</code>"
        )
        return

    items = []
    async with get_db() as db:
        for name in product_names:
            product = await get_product(db, name)
            if product is None:
                await message.answer(
                    f"Товар «{name}» не найден в каталоге. "
                    "Проверьте название командой /catalog."
                )
                return
            items.append(product)

    settings = {
        "company_name": getattr(config, "COMPANY_NAME", ""),
        "manager_contact": config.MANAGER_CONTACT,
        "delivery_zones": getattr(config, "DELIVERY_ZONES", "уточняйте у менеджера"),
    }

    try:
        pdf_bytes = generate_kp_pdf(client_name, items, settings)
    except Exception as e:
        logger.error("KP PDF generation failed: %s", e)
        await message.answer("Ошибка при создании КП. Попробуйте ещё раз.")
        return

    filename = f"kp_{client_name[:20].replace(' ', '_')}.pdf"
    await message.answer_document(
        BufferedInputFile(pdf_bytes, filename=filename),
        caption=f"КП для: {client_name}",
    )
