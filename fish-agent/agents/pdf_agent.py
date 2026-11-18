"""
PDFAgent: builds preis.pdf and kp.pdf from DB data.
"""
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from agents.memory_agent import get_client_by_name, get_preference
from agents.price_agent import get_best_prices
from config import settings
from memory.models import PreisVersion
from pdf.generator import pdf_checksum, render_kp, render_preis, save_pdf

logger = logging.getLogger(__name__)


async def build_preis_pdf(session: AsyncSession) -> str:
    """Build full price list PDF and return file path."""
    prices = await get_best_prices(session)

    company_name = await get_preference(session, "preis.my_name") or settings.company_name
    phone = await get_preference(session, "preis.my_phone") or settings.company_phone
    telegram = await get_preference(session, "preis.my_telegram") or settings.company_telegram
    conditions = await get_preference(session, "preis.conditions") or settings.company_conditions

    # Group by category
    products_by_category: dict[str, list[dict]] = {}
    article = 1
    for p in prices:
        if not p["my_price"] and not p["best_supplier_price"]:
            continue
        price_val = p["my_price"] or p["best_supplier_price"]
        cat = p["category"] or "прочее"
        name = p["product_name"]
        # Split "треска б/г" → name_base="треска", processing="б/г"
        parts = name.rsplit(" ", 1)
        name_base = parts[0] if len(parts) > 1 else name
        processing = parts[1] if len(parts) > 1 else ""

        products_by_category.setdefault(cat, []).append({
            "article": f"{article:03d}",
            "name_base": name_base,
            "processing": processing,
            "price_str": f"{price_val:.0f}" if price_val else "—",
        })
        article += 1

    pdf_bytes = render_preis(
        products_by_category=products_by_category,
        company_name=str(company_name),
        phone=str(phone or ""),
        telegram=str(telegram or ""),
        email=settings.company_email,
        conditions=str(conditions),
    )

    filename = f"preis_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    path = save_pdf(pdf_bytes, filename)

    version = PreisVersion(
        file_path=path,
        positions_count=article - 1,
        checksum=pdf_checksum(pdf_bytes),
    )
    session.add(version)
    await session.commit()

    logger.info("Preis PDF saved: %s (%d positions)", path, article - 1)
    return path


async def build_kp_pdf(session: AsyncSession, client_query: str) -> str | None:
    """Build commercial proposal PDF for a client by name. Returns path or None."""
    client = await get_client_by_name(session, client_query)
    if client is None:
        return None

    prices = await get_best_prices(session)

    company_name = await get_preference(session, "preis.my_name") or settings.company_name
    phone = await get_preference(session, "preis.my_phone") or settings.company_phone
    telegram = await get_preference(session, "preis.my_telegram") or settings.company_telegram
    conditions = await get_preference(session, "preis.conditions") or settings.company_conditions

    discount = float(client.discount_pct or 0) / 100
    items = []
    for p in prices:
        base_price = p["my_price"] or p["best_supplier_price"]
        if not base_price:
            continue
        final_price = float(base_price) * (1 - discount)
        items.append({
            "name": p["product_name"],
            "unit": p["unit"],
            "price_str": f"{final_price:.0f}",
        })

    pdf_bytes = render_kp(
        client_name=client.name,
        client_city=client.city or "",
        items=items,
        discount_pct=float(client.discount_pct or 0),
        min_order=float(client.min_order_kg) if client.min_order_kg else None,
        company_name=str(company_name),
        phone=str(phone or ""),
        telegram=str(telegram or ""),
        email=settings.company_email,
        conditions=str(conditions),
    )

    filename = f"kp_{client.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    path = save_pdf(pdf_bytes, filename)
    logger.info("KP PDF saved: %s", path)
    return path
