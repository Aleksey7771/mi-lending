"""
Парсер цен из Telegram-групп поставщиков.
Читает сообщения через MTProto API (Telethon).
Перед первым запуском нужна авторизация: python tg_reader/auth.py
"""

import logging
import re
from decimal import Decimal, InvalidOperation

from parsers.base import BaseParser, PriceRecord

logger = logging.getLogger(__name__)

# Ключевые слова рыбной тематики
_FISH_KEYWORDS = [
    "треска", "лосось", "горбуша", "кета", "нерка", "семга", "форель",
    "минтай", "палтус", "камбала", "терпуг", "навага", "сельдь",
    "скумбрия", "тунец", "хек", "пикша", "судак", "щука",
    "краб", "креветка", "кальмар", "осьминог", "мидия", "устрица",
    "икра", "морепродукт", "рыба", "филе", "б/г", "пбг", "нр",
    "мороженый", "свежемороженый", "охлаждённый",
]

# Паттерны поиска цены — захватывают число в группе 1
_PRICE_PATTERNS = [
    r"(\d[\d\s]{0,5})\s*(?:руб(?:лей?)?|₽|р\.?)(?:[./]кг)?",
    r"цена[:\s]+(\d+)",
    r"от\s+(\d+)\s*(?:руб|₽)",
    r"по\s+(\d+)\s*(?:руб|₽)",
]

_RE_FISH = [re.compile(k, re.IGNORECASE) for k in _FISH_KEYWORDS]
_RE_PRICE = [re.compile(p, re.IGNORECASE) for p in _PRICE_PATTERNS]


def _has_fish(text: str) -> bool:
    return any(r.search(text) for r in _RE_FISH)


def _extract_pairs(text: str) -> list[tuple[str, Decimal]]:
    """Парсит текст сообщения → список (сырое_название, цена)."""
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not _has_fish(line):
            continue
        for pat in _RE_PRICE:
            m = pat.search(line)
            if not m:
                continue
            try:
                price = Decimal(m.group(1).replace(" ", ""))
            except InvalidOperation:
                continue
            if not (10 <= price <= 500_000):
                continue
            raw_name = line[: m.start()].strip(" \t-–—:,")
            if raw_name:
                results.append((raw_name, price))
            break
    return results


class TelegramParser(BaseParser):
    source = "telegram"

    def __init__(self, api_id: int, api_hash: str, session_path: str, groups: list[str]):
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_path = session_path
        self._groups = groups

    # BaseParser требует fetch_raw/parse_raw, но мы полностью переопределяем parse()
    async def fetch_raw(self) -> str:  # type: ignore[override]
        return ""

    def parse_raw(self, raw: str) -> list[PriceRecord]:  # type: ignore[override]
        return []

    async def parse(self) -> list[PriceRecord]:
        # Импортируем Telethon здесь, чтобы бот стартовал даже без пакета
        try:
            from telethon import TelegramClient
            from telethon.tl.types import Message
        except ImportError:
            logger.error("Telethon не установлен: pip install telethon>=1.36.0")
            return []

        if not self._api_id or not self._api_hash:
            logger.warning("TG_API_ID / TG_API_HASH не заданы — TG парсер пропущен")
            return []

        if not self._groups:
            logger.warning("TG_GROUPS пуст — нечего читать")
            return []

        records: list[PriceRecord] = []
        client = TelegramClient(self._session_path, self._api_id, self._api_hash)

        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.error(
                    "Telethon сессия не авторизована. Запусти: "
                    "python tg_reader/auth.py"
                )
                await client.disconnect()
                return []

            for group in self._groups:
                group = group.strip().lstrip("@")
                try:
                    entity = await client.get_entity(group)
                    async for msg in client.iter_messages(entity, limit=300):
                        if not isinstance(msg, Message) or not msg.text:
                            continue
                        if not _has_fish(msg.text):
                            continue
                        pairs = _extract_pairs(msg.text)
                        url = f"https://t.me/{group}/{msg.id}"
                        for raw_name, price in pairs:
                            records.append(
                                PriceRecord(
                                    raw_name=raw_name,
                                    price_rub=price,
                                    source=f"telegram:{group}",
                                    source_url=url,
                                )
                            )
                    logger.info("TG @%s: извлечено %d записей", group, len(records))
                except Exception:
                    logger.exception("TG группа @%s: ошибка", group)

        finally:
            await client.disconnect()

        logger.info("TG парсер итого: %d ценовых записей", len(records))
        return records


def build_telegram_parser() -> "TelegramParser | None":
    """Создаёт парсер из настроек .env. Возвращает None если не настроен."""
    from config import settings

    if not settings.tg_api_id or not settings.tg_api_hash:
        return None

    groups = [g.strip() for g in settings.tg_groups.split(",") if g.strip()]
    if not groups:
        return None

    return TelegramParser(
        api_id=settings.tg_api_id,
        api_hash=settings.tg_api_hash,
        session_path=settings.tg_session_path,
        groups=groups,
    )
