"""
Импорт позиций и моих цен из Excel-прайса.
Использование: python scripts/import_my_prices.py [путь_к_файлу]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import openpyxl
from sqlalchemy import select

from memory.db import AsyncSessionFactory, engine
from memory.models import Base, MyPrice, Product

DEFAULT_FILE = r"C:\Users\User\Desktop\Прайс ТРД — рабочий.xlsx"


async def main() -> None:
    xlsx_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active

    products_added = 0
    prices_added = 0

    async with AsyncSessionFactory() as session:
        for row in ws.iter_rows(min_row=2, values_only=True):
            category = row[1]
            name = row[2]
            price_raw = row[12]
            availability = row[14] or ""

            if not name or not str(name).strip():
                continue

            name = str(name).strip()
            category = str(category).strip() if category else None

            # Найти или создать продукт
            product = await session.scalar(select(Product).where(Product.name == name))
            if not product:
                product = Product(name=name, category=category, unit="кг")
                session.add(product)
                await session.flush()
                products_added += 1

            # Добавить мою цену (только если есть числовая цена)
            if price_raw and isinstance(price_raw, (int, float)) and price_raw > 0:
                # Проверить нет ли уже актуальной цены
                existing = await session.scalar(
                    select(MyPrice)
                    .where(MyPrice.product_id == product.id)
                    .where(MyPrice.valid_until == None)
                )
                if not existing:
                    session.add(MyPrice(product_id=product.id, price_rub=float(price_raw)))
                    prices_added += 1

        await session.commit()

    print(f"Добавлено продуктов: {products_added}, цен: {prices_added}")
    print("Импорт завершён.")


if __name__ == "__main__":
    asyncio.run(main())
