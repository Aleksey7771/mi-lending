import json
import aiosqlite

_PUBLIC_COLUMNS = (
    "id", "name", "category", "form", "unit",
    "price_retail", "price_wholesale",
    "min_order_wholesale", "volume_tiers",
    "origin", "description", "photo_file_id",
    "in_stock", "seasonal_note",
    "created_at", "updated_at",
)

_ALL_COLUMNS = _PUBLIC_COLUMNS + ("price_vip",)


async def add_product(
    db: aiosqlite.Connection,
    name: str,
    category: str,
    price_retail: float,
    price_wholesale: float,
    **kwargs,
) -> int:
    if "volume_tiers" in kwargs and kwargs["volume_tiers"] is not None:
        try:
            json.loads(kwargs["volume_tiers"])
        except (json.JSONDecodeError, TypeError):
            raise ValueError("volume_tiers должен быть валидным JSON")

    cursor = await db.execute("SELECT id FROM products WHERE name = ?", (name,))
    if await cursor.fetchone():
        raise ValueError(f"Товар '{name}' уже существует")

    fields = {"name": name, "category": category,
               "price_retail": price_retail, "price_wholesale": price_wholesale}
    fields.update({k: v for k, v in kwargs.items() if v is not None})

    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    await db.execute(
        f"INSERT INTO products ({cols}) VALUES ({placeholders})",
        list(fields.values()),
    )
    await db.commit()

    cursor = await db.execute("SELECT last_insert_rowid()")
    row = await cursor.fetchone()
    return row[0]


async def get_product(db: aiosqlite.Connection, name: str) -> dict | None:
    cursor = await db.execute(
        "SELECT * FROM products WHERE name = ?", (name,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return dict(row)


async def get_all_products(
    db: aiosqlite.Connection, in_stock_only: bool = False
) -> list[dict]:
    if in_stock_only:
        cursor = await db.execute(
            "SELECT * FROM products WHERE in_stock = 1 ORDER BY category, name"
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM products ORDER BY category, name"
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_public_catalog(db: aiosqlite.Connection) -> list[dict]:
    cols = ", ".join(_PUBLIC_COLUMNS)
    cursor = await db.execute(
        f"SELECT {cols} FROM products WHERE in_stock = 1 ORDER BY category, name"
    )
    rows = await cursor.fetchall()
    return [dict(zip(_PUBLIC_COLUMNS, r)) for r in rows]


async def update_product(
    db: aiosqlite.Connection, product_id_or_name: str | int, **fields
) -> bool:
    if not fields:
        return False

    if "volume_tiers" in fields and fields["volume_tiers"] is not None:
        try:
            json.loads(fields["volume_tiers"])
        except (json.JSONDecodeError, TypeError):
            raise ValueError("volume_tiers должен быть валидным JSON")

    if isinstance(product_id_or_name, int):
        where_col, where_val = "id", product_id_or_name
    else:
        where_col, where_val = "name", product_id_or_name

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    set_clause += ", updated_at = CURRENT_TIMESTAMP"
    values = list(fields.values()) + [where_val]

    cursor = await db.execute(
        f"UPDATE products SET {set_clause} WHERE {where_col} = ?",
        values,
    )
    await db.commit()
    return cursor.rowcount > 0


async def set_stock(db: aiosqlite.Connection, name: str, in_stock: bool) -> bool:
    cursor = await db.execute(
        "UPDATE products SET in_stock = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
        (1 if in_stock else 0, name),
    )
    await db.commit()
    return cursor.rowcount > 0


async def find_product_fuzzy(db: aiosqlite.Connection, name_input: str) -> dict | None:
    """Поиск товара с учётом падежа: SQLite LOWER() не поддерживает кириллицу,
    поэтому сравниваем на стороне Python. Сначала точное совпадение, затем
    префиксный поиск (обрезаем 2 символа для русских падежных окончаний)."""
    cursor = await db.execute("SELECT * FROM products")
    rows = await cursor.fetchall()

    name_lower = name_input.lower()

    # Точное совпадение без учёта регистра
    for row in rows:
        if row["name"].lower() == name_lower:
            return dict(row)

    # Префиксный поиск: горбушу → горбуш
    prefix = name_lower[: max(3, len(name_lower) - 2)]
    for row in rows:
        if row["name"].lower().startswith(prefix):
            return dict(row)

    return None
