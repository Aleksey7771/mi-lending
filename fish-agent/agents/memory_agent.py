"""
MemoryAgent: read/write to PostgreSQL long-term memory.
"""
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.models import AgentMemory, Client, Product, Supplier, SupplierPrice
from parsers.fuzzy_match import normalize_product_name

logger = logging.getLogger(__name__)


async def save_supplier_price(
    session: AsyncSession,
    product_name_raw: str,
    price_rub: Decimal,
    supplier_name: str,
    source: str = "manual",
    source_url: str = "",
) -> dict:
    """
    Save a supplier price from manual input or parser.
    Returns confirmation dict with product/supplier names and status.
    """
    # Resolve product via fuzzy match
    products_rows = await session.execute(
        select(Product.id, Product.name, Product.aliases).where(Product.is_active == True)
    )
    products = [(r.id, r.name, r.aliases or []) for r in products_rows]
    match = normalize_product_name(product_name_raw, products)

    product_id: int | None = None
    canonical_name = product_name_raw
    if match:
        product_id = match.product_id
        canonical_name = match.canonical_name

    # Resolve supplier by name (fuzzy)
    suppliers_rows = await session.execute(
        select(Supplier.id, Supplier.name).where(Supplier.is_active == True)
    )
    all_suppliers = [(r.id, r.name) for r in suppliers_rows]
    supplier_id: int | None = None
    resolved_supplier = supplier_name
    for sid, sname in all_suppliers:
        if supplier_name.lower() in sname.lower() or sname.lower() in supplier_name.lower():
            supplier_id = sid
            resolved_supplier = sname
            break

    sp = SupplierPrice(
        supplier_id=supplier_id,
        product_id=product_id,
        price_rub=price_rub,
        source=source,
        source_url=source_url,
        raw_name=product_name_raw if product_id is None else None,
    )
    session.add(sp)
    await session.commit()

    return {
        "product": canonical_name,
        "price": price_rub,
        "supplier": resolved_supplier,
        "product_matched": product_id is not None,
        "supplier_matched": supplier_id is not None,
    }


async def get_preference(session: AsyncSession, key: str) -> object:
    mem = await session.get(AgentMemory, key)
    return mem.value if mem else None


async def set_preference(session: AsyncSession, key: str, value: object) -> None:
    mem = await session.get(AgentMemory, key)
    if mem:
        mem.value = value
    else:
        session.add(AgentMemory(key=key, value=value))
    await session.commit()


async def get_client_by_name(session: AsyncSession, name: str) -> Client | None:
    result = await session.execute(
        select(Client).where(Client.name.ilike(f"%{name}%"), Client.is_active == True)
    )
    return result.scalars().first()


async def save_supplier(
    session: AsyncSession, name: str, telegram: str = "", phone: str = "",
    region: str = "", notes: str = ""
) -> Supplier:
    supplier = Supplier(
        name=name,
        telegram=telegram or None,
        phone=phone or None,
        region=region or None,
        notes=notes or None,
    )
    session.add(supplier)
    await session.commit()
    return supplier


async def save_client(
    session: AsyncSession, name: str, client_type: str = "",
    city: str = "", phone: str = "", notes: str = ""
) -> Client:
    client = Client(
        name=name,
        type=client_type or None,
        city=city or None,
        phone=phone or None,
        notes=notes or None,
    )
    session.add(client)
    await session.commit()
    return client
