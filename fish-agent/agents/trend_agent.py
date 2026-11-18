"""
TrendAgent: price history analysis and ASCII trend charts.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from memory.models import Product, Supplier, SupplierPrice
from parsers.fuzzy_match import normalize_product_name

logger = logging.getLogger(__name__)

# Unicode block chars for ASCII bar chart
BLOCKS = " ▁▂▃▄▅▆▇█"


def _bar(value: float, min_val: float, max_val: float, width: int = 8) -> str:
    if max_val == min_val:
        return "▄" * (width // 2)
    ratio = (value - min_val) / (max_val - min_val)
    filled = int(ratio * width)
    block_idx = min(int(ratio * 8), 8)
    return "█" * filled + BLOCKS[block_idx] + " " * (width - filled)


async def get_price_history(
    session: AsyncSession,
    product_name: str,
    days: int = 30,
) -> dict | None:
    """
    Get price history for a product over N days.
    Returns dict with product info, daily averages, min/max/current.
    """
    # Fuzzy match product
    products_rows = await session.execute(
        select(Product.id, Product.name, Product.aliases).where(Product.is_active == True)
    )
    products = [(r.id, r.name, r.aliases or []) for r in products_rows]
    match = normalize_product_name(product_name, products)
    if not match:
        return None

    product_id = match.product_id
    canonical_name = match.canonical_name
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Daily averages (best price per day)
    rows = (await session.execute(
        select(
            func.date(SupplierPrice.recorded_at).label("day"),
            func.min(SupplierPrice.price_rub).label("min_price"),
            func.avg(SupplierPrice.price_rub).label("avg_price"),
            func.count().label("cnt"),
        )
        .where(
            SupplierPrice.product_id == product_id,
            SupplierPrice.recorded_at >= cutoff,
        )
        .group_by(func.date(SupplierPrice.recorded_at))
        .order_by(func.date(SupplierPrice.recorded_at))
    )).all()

    if not rows:
        return {"product": canonical_name, "no_data": True}

    daily = [
        {"day": str(r.day), "min": float(r.min_price), "avg": float(r.avg_price), "cnt": r.cnt}
        for r in rows
    ]

    # Best current supplier
    best_now = (await session.execute(
        select(SupplierPrice, Supplier.name)
        .join(Supplier, SupplierPrice.supplier_id == Supplier.id, isouter=True)
        .where(
            SupplierPrice.product_id == product_id,
            SupplierPrice.recorded_at >= datetime.utcnow() - timedelta(hours=48),
        )
        .order_by(SupplierPrice.price_rub)
        .limit(1)
    )).first()

    prices = [d["min"] for d in daily]
    first_price = prices[0]
    last_price = prices[-1]
    change_pct = (last_price - first_price) / first_price * 100 if first_price else 0

    return {
        "product": canonical_name,
        "days": days,
        "daily": daily,
        "min_all": min(prices),
        "max_all": max(prices),
        "current": last_price,
        "first": first_price,
        "change_pct": change_pct,
        "best_supplier": best_now[1] if best_now else None,
        "best_price": float(best_now[0].price_rub) if best_now else None,
        "data_points": len(daily),
    }


def format_trend_message(data: dict) -> str:
    """Format price history as a Telegram message with ASCII chart."""
    if data.get("no_data"):
        return f"📊 <b>{data['product']}</b>\n\nДанных нет — цены ещё не поступали."

    product = data["product"]
    days = data["days"]
    daily = data["daily"]
    min_all = data["min_all"]
    max_all = data["max_all"]
    current = data["current"]
    change_pct = data["change_pct"]

    lines = [f"📊 <b>{product}</b> — тренд за {days} дней\n"]

    # Change summary
    if abs(change_pct) < 1:
        trend_line = "→ Цена стабильна"
    elif change_pct > 0:
        trend_line = f"📈 +{change_pct:.1f}% за период ({data['first']:.0f}₽ → {current:.0f}₽)"
    else:
        trend_line = f"📉 {change_pct:.1f}% за период ({data['first']:.0f}₽ → {current:.0f}₽)"

    lines.append(trend_line)
    lines.append(f"Диапазон: {min_all:.0f}₽ — {max_all:.0f}₽/кг\n")

    # ASCII chart — show last 14 points max (fits in Telegram)
    chart_data = daily[-14:]
    if len(chart_data) >= 2:
        lines.append("<b>График (мин. цена/день):</b>")
        lines.append("<code>")
        chart_min = min(d["min"] for d in chart_data)
        chart_max = max(d["min"] for d in chart_data)

        for d in chart_data:
            day_short = d["day"][5:]  # MM-DD
            bar = _bar(d["min"], chart_min, chart_max, width=10)
            lines.append(f"{day_short} {bar} {d['min']:.0f}₽")

        lines.append("</code>")

    # Current best
    if data.get("best_supplier"):
        lines.append(f"\n💰 Сейчас лучший: <b>{data['best_price']:.0f}₽</b> у {data['best_supplier']}")

    lines.append(f"\n<i>Данных за период: {data['data_points']} дней</i>")
    return "\n".join(lines)
