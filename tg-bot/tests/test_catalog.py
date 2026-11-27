import pytest
from db.catalog import (
    add_product,
    get_product,
    get_all_products,
    get_public_catalog,
    update_product,
    set_stock,
)


async def test_add_and_get_product(db):
    pid = await add_product(
        db,
        name="Горбуша",
        category="рыба",
        price_retail=250.0,
        price_wholesale=185.0,
        origin="Камчатка",
    )
    assert isinstance(pid, int)
    product = await get_product(db, "Горбуша")
    assert product["name"] == "Горбуша"
    assert product["price_wholesale"] == 185.0
    assert product["origin"] == "Камчатка"


async def test_public_catalog_hides_vip_price(db):
    await add_product(
        db,
        name="Икра",
        category="икра",
        price_retail=3200.0,
        price_wholesale=2900.0,
        price_vip=2500.0,
    )
    catalog = await get_public_catalog(db)
    item = next(p for p in catalog if p["name"] == "Икра")
    assert "price_vip" not in item


async def test_update_price(db):
    await add_product(
        db,
        name="Минтай",
        category="рыба",
        price_retail=100.0,
        price_wholesale=80.0,
    )
    updated = await update_product(db, "Минтай", price_wholesale=85.0)
    assert updated is True
    p = await get_product(db, "Минтай")
    assert p["price_wholesale"] == 85.0


async def test_duplicate_name_raises(db):
    await add_product(
        db,
        name="Треска",
        category="рыба",
        price_retail=200.0,
        price_wholesale=160.0,
    )
    with pytest.raises(ValueError, match="уже существует"):
        await add_product(
            db,
            name="Треска",
            category="рыба",
            price_retail=210.0,
            price_wholesale=165.0,
        )


async def test_invalid_volume_tiers_json(db):
    with pytest.raises(ValueError, match="volume_tiers"):
        await add_product(
            db,
            name="Кета",
            category="рыба",
            price_retail=300.0,
            price_wholesale=240.0,
            volume_tiers="not-json",
        )


async def test_set_stock(db):
    await add_product(
        db,
        name="Нерка",
        category="рыба",
        price_retail=400.0,
        price_wholesale=320.0,
    )
    result = await set_stock(db, "Нерка", False)
    assert result is True
    p = await get_product(db, "Нерка")
    assert p["in_stock"] == 0


async def test_get_all_products_in_stock_filter(db):
    await add_product(db, name="Чавыча", category="рыба",
                      price_retail=800.0, price_wholesale=650.0)
    await add_product(db, name="Кижуч", category="рыба",
                      price_retail=600.0, price_wholesale=480.0)
    await set_stock(db, "Кижуч", False)

    all_products = await get_all_products(db, in_stock_only=False)
    in_stock = await get_all_products(db, in_stock_only=True)

    names_all = {p["name"] for p in all_products}
    names_in = {p["name"] for p in in_stock}
    assert "Чавыча" in names_all and "Кижуч" in names_all
    assert "Чавыча" in names_in and "Кижуч" not in names_in
