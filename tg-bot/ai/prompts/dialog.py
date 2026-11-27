import json
import config

_PUBLIC_CATALOG_KEYS = (
    "name", "category", "form", "unit",
    "price_retail", "price_wholesale",
    "min_order_wholesale", "origin", "in_stock",
)


def build_dialog_prompt(
    message: str,
    catalog: list[dict],
    settings: dict,
) -> list[dict]:
    # Никогда не передаём price_vip в промпт
    public_catalog = [
        {k: v for k, v in item.items() if k != "price_vip"}
        for item in catalog
        if item.get("in_stock")
    ]

    delivery_str = json.dumps(settings, ensure_ascii=False, indent=2) if settings else "нет данных"

    system = (
        "Ты — помощник продавца морепродуктов. Отвечаешь вежливо и по делу.\n"
        "Работаешь СТРОГО по предоставленным данным. Никогда не придумываешь цены, "
        "условия и наличие.\n"
        f"Если клиент спрашивает индивидуальную цену — отвечай общим прайсом "
        f"и предлагай обратиться к менеджеру: {config.MANAGER_CONTACT}.\n"
        f"Если вопрос не в данных — отвечай «уточню у менеджера и отвечу "
        f"в течение {config.RESPONSE_TIME_HOURS} ч.»\n\n"
        f"Каталог (только в наличии):\n{json.dumps(public_catalog, ensure_ascii=False, indent=2)}\n\n"
        f"Настройки доставки:\n{delivery_str}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]
