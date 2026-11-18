import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.db import AsyncSessionFactory
from memory.models import Product, Supplier, SupplierPrice
from parsers.fishery import FisheryParser
from parsers.fishnet import FishnetParser
from parsers.fishretail import FishretailParser
from parsers.fuzzy_match import normalize_product_name
from parsers.telegram_parser import build_telegram_parser

logger = logging.getLogger(__name__)


async def run_parsers() -> int:
    """Run all web parsers and save results to DB."""
    parsers = [FishnetParser(), FishretailParser(), FisheryParser()]

    tg_parser = build_telegram_parser()
    if tg_parser:
        parsers.append(tg_parser)
        logger.info("TelegramParser добавлен (%d групп)", len(tg_parser._groups))

    async with AsyncSessionFactory() as session:
        # Load product catalog for fuzzy matching
        products_rows = await session.execute(
            select(Product.id, Product.name, Product.aliases).where(Product.is_active == True)
        )
        products = [(r.id, r.name, r.aliases or []) for r in products_rows]

        # Load supplier name → id mapping
        suppliers_rows = await session.execute(
            select(Supplier.id, Supplier.name).where(Supplier.is_active == True)
        )
        supplier_map = {s.name.lower(): s.id for s in suppliers_rows}

        total_saved = 0
        for parser in parsers:
            try:
                records = await parser.parse()
                for rec in records:
                    match = normalize_product_name(rec.raw_name, products)
                    product_id = match.product_id if match else None

                    # Find supplier
                    supplier_id = None
                    if rec.supplier_name:
                        for sname, sid in supplier_map.items():
                            if rec.supplier_name.lower() in sname or sname in rec.supplier_name.lower():
                                supplier_id = sid
                                break

                    sp = SupplierPrice(
                        product_id=product_id,
                        supplier_id=supplier_id,
                        price_rub=rec.price_rub,
                        source=rec.source,
                        source_url=rec.source_url,
                        raw_name=rec.raw_name if product_id is None else None,
                    )
                    session.add(sp)
                    total_saved += 1

                await session.commit()
                logger.info("%s: saved %d price records", parser.source, len(records))
            except Exception:
                logger.exception("Parser %s failed", parser.source)

    logger.info("Price update done. Total saved: %d", total_saved)
    return total_saved


async def run_fishery_parser() -> int:
    """Run only the fishery.ru parser (called on its own 2h schedule)."""
    async with AsyncSessionFactory() as session:
        products_rows = await session.execute(
            select(Product.id, Product.name, Product.aliases).where(Product.is_active == True)
        )
        products = [(r.id, r.name, r.aliases or []) for r in products_rows]
        suppliers_rows = await session.execute(
            select(Supplier.id, Supplier.name).where(Supplier.is_active == True)
        )
        supplier_map = {s.name.lower(): s.id for s in suppliers_rows}

        total_saved = 0
        try:
            records = await FisheryParser().parse()
            for rec in records:
                match = normalize_product_name(rec.raw_name, products)
                product_id = match.product_id if match else None
                supplier_id = None
                if rec.supplier_name:
                    for sname, sid in supplier_map.items():
                        if rec.supplier_name.lower() in sname or sname in rec.supplier_name.lower():
                            supplier_id = sid
                            break
                sp = SupplierPrice(
                    product_id=product_id,
                    supplier_id=supplier_id,
                    price_rub=rec.price_rub,
                    source=rec.source,
                    source_url=rec.source_url,
                    raw_name=rec.raw_name if product_id is None else None,
                )
                session.add(sp)
                total_saved += 1
            await session.commit()
            logger.info("fishery job: saved %d records", total_saved)
        except Exception:
            logger.exception("fishery job failed")

    return total_saved
