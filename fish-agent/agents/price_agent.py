"""
PriceAgent: best prices, morning digest, price comparison.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.models import MyPrice, Product, Supplier, SupplierPrice

logger = logging.getLogger(__name__)


async def get_best_prices(session: AsyncSession) -> list[dict]:
    """Return the best (lowest) current supplier price per active product."""
    products = (await session.execute(
        select(Product).where(Product.is_active == True).order_by(Product.category, Product.name)
    )).scalars().all()

    result = []
    cutoff = datetime.utcnow() - timedelta(hours=48)

    for product in products:
        rows = await session.execute(
            select(SupplierPrice, Supplier.name)
            .join(Supplier, SupplierPrice.supplier_id == Supplier.id, isouter=True)
            .where(
                SupplierPrice.product_id == product.id,
                SupplierPrice.recorded_at >= cutoff,
            )
            .order_by(SupplierPrice.price_rub)
            .limit(1)
        )
        row = rows.first()
        my_price = await _get_my_price(session, product.id)

        result.append({
            "product_id": product.id,
            "product_name": product.name,
            "category": product.category,
            "unit": product.unit,
            "best_supplier_price": row[0].price_rub if row else None,
            "best_supplier_name": row[1] if row else None,
            "best_price_at": row[0].recorded_at if row else None,
            "best_price_source": row[0].source if row else None,
            "my_price": my_price,
            "data_fresh": row is not None,
        })

    return result


async def _get_my_price(session: AsyncSession, product_id: int) -> Decimal | None:
    row = await session.execute(
        select(MyPrice.price_rub)
        .where(MyPrice.product_id == product_id)
        .order_by(MyPrice.valid_from.desc())
        .limit(1)
    )
    return row.scalar()


async def get_price_changes(session: AsyncSession) -> list[dict]:
    """Compare best prices now vs 24h ago, return items with significant changes."""
    products = (await session.execute(
        select(Product).where(Product.is_active == True)
    )).scalars().all()

    now = datetime.utcnow()
    window_now = now - timedelta(hours=24)
    window_prev = now - timedelta(hours=48)

    changes = []
    for product in products:
        # Best price in last 24h
        row_now = (await session.execute(
            select(SupplierPrice, Supplier.name)
            .join(Supplier, SupplierPrice.supplier_id == Supplier.id, isouter=True)
            .where(
                SupplierPrice.product_id == product.id,
                SupplierPrice.recorded_at >= window_now,
            )
            .order_by(SupplierPrice.price_rub)
            .limit(1)
        )).first()

        # Best price 24–48h ago
        row_prev = (await session.execute(
            select(SupplierPrice, Supplier.name)
            .join(Supplier, SupplierPrice.supplier_id == Supplier.id, isouter=True)
            .where(
                SupplierPrice.product_id == product.id,
                SupplierPrice.recorded_at >= window_prev,
                SupplierPrice.recorded_at < window_now,
            )
            .order_by(SupplierPrice.price_rub)
            .limit(1)
        )).first()

        if not row_now or not row_prev:
            continue

        price_now = float(row_now[0].price_rub)
        price_prev = float(row_prev[0].price_rub)
        pct = (price_now - price_prev) / price_prev * 100

        if abs(pct) >= 3:  # только заметные изменения >=3%
            changes.append({
                "product": product.name,
                "supplier": row_now[1] or "—",
                "price_now": price_now,
                "price_prev": price_prev,
                "pct": pct,
            })

    changes.sort(key=lambda x: abs(x["pct"]), reverse=True)
    return changes


async def format_morning_digest(session: AsyncSession) -> str:
    """Build the morning digest message text — full version per spec."""
    prices = await get_best_prices(session)
    changes = await get_price_changes(session)
    now = datetime.now()

    lines = [f"📊 <b>Доброе утро. Сводка на {now.strftime('%d.%m.%Y')}, {now.strftime('%H:%M')}</b>\n"]

    # --- Изменения с вчера ---
    if changes:
        lines.append("📈 <b>Изменения с вчера:</b>")
        for c in changes[:5]:
            arrow = "📈" if c["pct"] > 0 else "📉"
            sign = "+" if c["pct"] > 0 else ""
            lines.append(
                f"  {arrow} {c['product']} {sign}{c['pct']:.0f}% у {c['supplier']} "
                f"({c['price_prev']:.0f}₽ → {c['price_now']:.0f}₽)"
            )
        lines.append("")

    # --- Лучшие цены по позициям ---
    by_category: dict[str, list[dict]] = {}
    stale_products = []
    no_data_products = []

    for p in prices:
        if not p["my_price"] and not p["best_supplier_price"]:
            continue
        cat = p["category"] or "Прочее"
        by_category.setdefault(cat, []).append(p)

        if not p["data_fresh"]:
            if p["best_supplier_price"]:
                stale_products.append(p["product_name"])
            else:
                no_data_products.append(p["product_name"])

    if by_category:
        lines.append("💰 <b>Лучшие цены сейчас:</b>")
        for cat, items in sorted(by_category.items()):
            lines.append(f"\n<b>{cat}</b>")
            for item in items:
                price_val = item["best_supplier_price"] or item["my_price"]
                price_str = f"{price_val:.0f}₽/кг"
                supplier = item["best_supplier_name"] or "—"
                freshness = ""
                if item["best_price_at"]:
                    age_h = (datetime.utcnow() - item["best_price_at"]).total_seconds() / 3600
                    if age_h < 2:
                        freshness = f" <i>(обновл. {item['best_price_at'].strftime('%H:%M')})</i>"
                    elif age_h < 24:
                        freshness = f" <i>({age_h:.0f}ч назад)</i>"
                    else:
                        freshness = f" <i>(вчера)</i>"
                my = ""
                if item["my_price"]:
                    my = f" → моя: <b>{item['my_price']:.0f}₽</b>"
                lines.append(f"  • {item['product_name']}: {price_str} {supplier}{freshness}{my}")
    else:
        # Нет цен поставщиков — показываем хотя бы мои цены
        lines.append("💰 <b>Мой прайс:</b>")
        for p in prices:
            if p["my_price"]:
                cat = p["category"] or "Прочее"
                lines.append(f"  • {p['product_name']} — {p['my_price']:.0f}₽/кг")

    # --- Алерты по устаревшим данным ---
    if stale_products:
        lines.append(
            f"\n⚠️ Данные старше 48ч ({len(stale_products)} поз.): "
            + ", ".join(stale_products[:5])
            + (f" и ещё {len(stale_products)-5}" if len(stale_products) > 5 else "")
        )
    if no_data_products:
        lines.append(
            f"❌ Нет данных ({len(no_data_products)} поз.): "
            + ", ".join(no_data_products[:5])
            + (f" и ещё {len(no_data_products)-5}" if len(no_data_products) > 5 else "")
        )

    return "\n".join(lines)
