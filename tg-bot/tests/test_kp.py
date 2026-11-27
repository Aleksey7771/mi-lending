from pdf.kp_generator import generate_kp_pdf

ITEMS = [
    {"name": "Горбуша б/г", "origin": "Камчатка",
     "price_wholesale": 185.0, "unit": "кг", "min_order_wholesale": 5},
    {"name": "Икра горбуши", "origin": "Сахалин",
     "price_wholesale": 2900.0, "unit": "кг", "min_order_wholesale": 2},
]
SETTINGS = {
    "company_name": "ИП Тест",
    "manager_contact": "@test_manager",
    "delivery_zones": "Владивосток, Хабаровск",
}


def test_generate_kp_pdf_returns_bytes():
    result = generate_kp_pdf("ООО Тест", ITEMS, SETTINGS)
    assert isinstance(result, bytes)
    assert len(result) > 1000


def test_generate_kp_pdf_multiple_items():
    result = generate_kp_pdf("Ресторан Якорь", ITEMS, SETTINGS)
    assert isinstance(result, bytes)
    assert len(result) > 1000


def test_generate_kp_pdf_no_vip_price():
    items_with_vip = [{**ITEMS[0], "price_vip": 120.0}]
    result = generate_kp_pdf("Тест", items_with_vip, SETTINGS)
    assert isinstance(result, bytes)
    assert len(result) > 100
