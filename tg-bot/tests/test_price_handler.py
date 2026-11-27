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
