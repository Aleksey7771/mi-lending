"""
Однократный импорт CSV-файлов в БД.
Использование: python scripts/import_csv.py

Запускать после: docker compose up -d postgres && alembic upgrade head
"""
import asyncio
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.db import AsyncSessionFactory, engine
from memory.models import Base, Client, Product, Supplier


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


async def import_products(session: AsyncSession) -> int:
    path = os.path.join(DATA_DIR, "products.csv")
    count = 0
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if not name:
                continue
            existing = await session.scalar(select(Product).where(Product.name == name))
            if existing:
                continue
            aliases_raw = row.get("aliases", "").strip()
            aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()] if aliases_raw else []
            product = Product(
                name=name,
                category=row.get("category", "").strip() or None,
                aliases=aliases,
                unit=row.get("unit", "кг").strip() or "кг",
                season_note=row.get("season_note", "").strip() or None,
            )
            session.add(product)
            count += 1
    await session.commit()
    return count


async def import_suppliers(session: AsyncSession) -> int:
    path = os.path.join(DATA_DIR, "suppliers.csv")
    count = 0
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if not name:
                continue
            existing = await session.scalar(select(Supplier).where(Supplier.name == name))
            if existing:
                continue
            supplier = Supplier(
                name=name,
                telegram=row.get("telegram", "").strip() or None,
                phone=row.get("phone", "").strip() or None,
                email=row.get("email", "").strip() or None,
                region=row.get("region", "").strip() or None,
                notes=row.get("notes", "").strip() or None,
            )
            session.add(supplier)
            count += 1
    await session.commit()
    return count


async def import_clients(session: AsyncSession) -> int:
    path = os.path.join(DATA_DIR, "clients.csv")
    count = 0
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if not name:
                continue
            existing = await session.scalar(select(Client).where(Client.name == name))
            if existing:
                continue

            def optional_decimal(val: str):
                v = val.strip()
                return float(v) if v else None

            client = Client(
                name=name,
                type=row.get("type", "").strip() or None,
                telegram=row.get("telegram", "").strip() or None,
                phone=row.get("phone", "").strip() or None,
                email=row.get("email", "").strip() or None,
                city=row.get("city", "").strip() or None,
                min_order_kg=optional_decimal(row.get("min_order_kg", "")),
                discount_pct=optional_decimal(row.get("discount_pct", "")) or 0,
                notes=row.get("notes", "").strip() or None,
            )
            session.add(client)
            count += 1
    await session.commit()
    return count


async def seed_agent_memory(session: AsyncSession) -> None:
    from memory.models import AgentMemory
    defaults = {
        "style.tone": "Деловой, без пафоса. Короткие предложения. Конкретные цифры.",
        "style.avoid": ["восклицательные знаки", "слово 'уникальный'", "сроки хранения"],
        "preis.my_name": os.environ.get("COMPANY_NAME", "ИП Иванов"),
        "preis.my_phone": os.environ.get("COMPANY_PHONE", ""),
        "preis.my_telegram": os.environ.get("COMPANY_TELEGRAM", ""),
        "preis.conditions": os.environ.get(
            "COMPANY_CONDITIONS", "Минимальный заказ 50 кг."
        ),
        "schedule.morning_hour": int(os.environ.get("MORNING_DIGEST_HOUR", 9)),
        "schedule.morning_tz": os.environ.get("MORNING_DIGEST_TZ", "Asia/Vladivostok"),
    }
    for key, value in defaults.items():
        existing = await session.get(AgentMemory, key)
        if not existing:
            session.add(AgentMemory(key=key, value=value))
    await session.commit()


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionFactory() as session:
        p = await import_products(session)
        s = await import_suppliers(session)
        c = await import_clients(session)
        await seed_agent_memory(session)
        print(f"Импортировано: {p} позиций, {s} поставщиков, {c} клиентов.")
        print("Настройки агента записаны в agent_memory.")


if __name__ == "__main__":
    asyncio.run(main())
