import json

_DEFAULT_STYLE = {
    "tone": "professional",
    "emoji_density": "low",
    "length": "medium",
    "cta_style": "soft",
    "sample_good": [],
}

_EMOJI_DENSITY_MAP = {
    "none": "Не используй эмодзи.",
    "low": "Используй 1-2 эмодзи максимум.",
    "medium": "Используй эмодзи умеренно (3-5 на пост).",
    "high": "Используй эмодзи активно.",
}

_TONE_MAP = {
    "professional": "деловой и профессиональный, без лишних слов",
    "casual": "неформальный, от лица автора, с личной историей",
    "mixed": "профессиональный с лёгкой эмоцией",
}

_LENGTH_MAP = {
    "short": "Краткий пост — 3-5 строк.",
    "medium": "Пост средней длины — 7-10 строк.",
    "long": "Развёрнутый пост — до 15 строк.",
}

_CTA_MAP = {
    "soft": "Мягкий призыв: 'Уточнить у менеджера' или 'Пишите в личку'.",
    "hard": "Активный призыв: 'Заказывайте сейчас!' или 'Звоните!'.",
}


def build_post_prompt(
    product: dict,
    command: str,
    style_profile: dict | None,
) -> list[dict]:
    style = style_profile or _DEFAULT_STYLE

    tone_desc = _TONE_MAP.get(style.get("tone", "professional"), _TONE_MAP["professional"])
    emoji_desc = _EMOJI_DENSITY_MAP.get(style.get("emoji_density", "low"), _EMOJI_DENSITY_MAP["low"])
    length_desc = _LENGTH_MAP.get(style.get("length", "medium"), _LENGTH_MAP["medium"])
    cta_desc = _CTA_MAP.get(style.get("cta_style", "soft"), _CTA_MAP["soft"])

    samples = style.get("sample_good", [])
    samples_block = ""
    if samples:
        joined = "\n---\n".join(samples[:3])
        samples_block = f"\nВот примеры постов, которые понравились:\n{joined}\n"

    system = (
        "Ты — маркетолог для оптового продавца морепродуктов с Дальнего Востока.\n"
        "Пиши на русском языке.\n"
        f"Тон: {tone_desc}.\n"
        f"{emoji_desc}\n"
        f"{length_desc}\n"
        "Всегда упоминай происхождение товара. Всегда указывай цену (только из данных).\n"
        "Не придумывай факты о товаре — только то, что есть в описании.\n"
        f"{cta_desc}\n"
        f"{samples_block}"
    )

    # Strip price_vip — never leaks into the prompt
    public_product = {k: v for k, v in product.items() if k != "price_vip"}

    user = (
        f"Команда: {command}\n"
        f"Данные товара:\n{json.dumps(public_product, ensure_ascii=False, indent=2)}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
