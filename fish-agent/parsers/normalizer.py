import re
from decimal import Decimal, InvalidOperation


def normalize_price(raw: str) -> Decimal | None:
    """
    Extract a price from a raw string like '182₽', '182 руб', '182.50/кг'.
    Returns Decimal or None.
    """
    raw = raw.replace("₽", "").replace("руб", "").replace("р.", "").strip()
    # Remove trailing units like /кг, /kg
    raw = re.sub(r"/.*$", "", raw).strip()
    # Keep digits and decimal separator
    raw = re.sub(r"[^\d.,]", "", raw).replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def normalize_unit(raw: str) -> str:
    """Normalize weight unit to 'кг' or 'шт'."""
    raw = raw.lower().strip()
    if raw in ("кг", "kg", "кило", "kilogram"):
        return "кг"
    if raw in ("шт", "шт.", "pcs", "штука"):
        return "шт"
    return "кг"  # default
