"""Message templates for daily_price and weekly_promo."""
from datetime import date

_MONTHS_RU = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _ru_date(d: date | None = None) -> str:
    d = d or date.today()
    return f"{d.day} {_MONTHS_RU[d.month - 1]}"


def render_daily_price(prices: list) -> str:
    """
    prices: list of rows with .name, .price_rub, .unit
    Returns formatted daily price message (plain text, no HTML).
    """
    lines = [f"🐟 Прайс дня — {_ru_date()}\n"]
    for row in prices:
        unit = getattr(row, "unit", None) or "кг"
        price = int(row.price_rub) if row.price_rub == int(row.price_rub) else float(row.price_rub)
        lines.append(f"{row.name} — {price}₽/{unit}")
    lines.append(f"\n📞 +7 914 326 50 50 | ТРД Владивосток")
    return "\n".join(lines)


def render_weekly_promo_prompt(company_name: str, company_phone: str) -> str:
    """Returns the Claude prompt for generating weekly_promo content."""
    return (
        f"Напиши рекламное сообщение для оптового покупателя рыбы и мяса "
        f"от компании «{company_name}».\n"
        "Стиль: деловой, без спама эмодзи (1-2 максимум), убедительный.\n"
        "Включи: преимущества работы с нами, широкий ассортимент, "
        "доставка по Владивостоку и Приморскому краю.\n"
        f"В конце укажи контакт: {company_phone}.\n"
        "Длина: 3-5 предложений. Не используй слово «уникальный»."
    )
