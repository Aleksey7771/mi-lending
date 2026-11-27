from handlers.price import format_price_list


def test_format_price_list_basic():
    products = [
        {"name": "Горбуша", "category": "рыба", "price_retail": 250.0,
         "price_wholesale": 185.0, "price_vip": 160.0, "unit": "кг",
         "origin": "Камчатка", "in_stock": 1},
        {"name": "Икра", "category": "икра", "price_retail": 3200.0,
         "price_wholesale": 2900.0, "price_vip": None, "unit": "кг",
         "origin": "Сахалин", "in_stock": 1},
    ]
    result = format_price_list(products)
    assert "Горбуша" in result
    assert "185" in result
    assert "250" in result
    assert "160" not in result  # price_vip не должен попасть


def test_format_price_list_no_vip_leak():
    products = [{"name": "X", "category": "рыба", "price_retail": 100.0,
                 "price_wholesale": 80.0, "price_vip": 55.0,
                 "unit": "кг", "origin": "Камчатка", "in_stock": 1}]
    result = format_price_list(products)
    assert "55" not in result


def test_format_price_list_empty():
    result = format_price_list([])
    lower = result.lower()
    assert "нет" in lower or result.strip() == "" or "пуст" in lower


async def test_cmd_price_calls_update_data_not_update():
    """state.update_data() is the correct aiogram 3 FSMContext method, not state.update()."""
    from unittest.mock import AsyncMock, MagicMock, patch
    products = [
        {"name": "Горбуша", "category": "рыба", "price_retail": 250.0,
         "price_wholesale": 185.0, "price_vip": None, "unit": "кг",
         "origin": "Камчатка", "in_stock": 1},
    ]
    msg = MagicMock()
    msg.answer = AsyncMock()
    state = AsyncMock()

    with patch("handlers.price.get_public_catalog", new_callable=AsyncMock,
               return_value=products):
        from handlers.price import cmd_price
        await cmd_price(msg, state=state)

    state.update_data.assert_awaited()
    state.update.assert_not_awaited()


async def test_price_correction_accusative_finds_product(db):
    """'горбушу на 480' должно найти товар 'Горбуша' (винит. падеж → номинатив)."""
    from db.catalog import add_product, find_product_fuzzy
    await add_product(db, name="Горбуша", category="рыба",
                      price_retail=250.0, price_wholesale=185.0)
    result = await find_product_fuzzy(db, "горбушу")
    assert result is not None
    assert result["name"] == "Горбуша"


async def test_price_correction_exact_name_works(db):
    """Точное совпадение (номинатив) тоже работает."""
    from db.catalog import add_product, find_product_fuzzy
    await add_product(db, name="Икра горбуши", category="икра",
                      price_retail=3200.0, price_wholesale=2900.0)
    result = await find_product_fuzzy(db, "Икра горбуши")
    assert result is not None
    assert result["name"] == "Икра горбуши"


async def test_price_correction_missing_product_returns_none(db):
    """Несуществующий товар возвращает None."""
    from db.catalog import find_product_fuzzy
    result = await find_product_fuzzy(db, "кальмар")
    assert result is None


def test_format_price_list_groups_by_category():
    products = [
        {"name": "Горбуша", "category": "рыба", "price_retail": 250.0,
         "price_wholesale": 185.0, "price_vip": None, "unit": "кг",
         "origin": "Камчатка", "in_stock": 1},
        {"name": "Икра горбуши", "category": "икра", "price_retail": 3200.0,
         "price_wholesale": 2900.0, "price_vip": None, "unit": "кг",
         "origin": "Сахалин", "in_stock": 1},
    ]
    result = format_price_list(products)
    assert result.index("РЫБА") < result.index("Горбуша")
    assert result.index("ИКРА") < result.index("Икра горбуши")
