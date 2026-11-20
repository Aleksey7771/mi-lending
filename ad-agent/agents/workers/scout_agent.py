"""Scout agent — monitors Telegram groups for competitor prices via Telethon.

Strategy:
  - Tracks last read message_id per group in agent_memory table
  - On each run reads only NEW messages (min_id = last_id + 1)
  - Extracts multiple product+price pairs per message
  - Saves each pair as a separate row in price_intel
  - Fuzzy-matches product names against products table (rapidfuzz)
"""
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from agents.state import AgentState

logger = logging.getLogger(__name__)

# ── Price regex patterns (Russian fish/meat wholesale formats) ────────────────

# "182 руб/кг"  "95 р/кг"  "450₽/кг"  "380 руб.кг"  "240р."
_P1 = re.compile(
    r"(\d[\d\s]{0,6}(?:[.,]\d{1,2})?)"
    r"\s*(?:руб(?:лей)?\.?|р\.?|₽)"
    r"(?:\s*/?\s*(?:кг|kg))?",
    re.IGNORECASE,
)

# "240/кг"  "95 / кг"
_P2 = re.compile(r"(\d[\d\s]{0,6}(?:[.,]\d{1,2})?)\s*/\s*(?:кг|kg)", re.IGNORECASE)

# "= 850р"  "=850"  ": 450"  "— 182"  "- 95"
_P3 = re.compile(
    r"(?:=|:|-|–|—)\s*(\d[\d\s]{0,6}(?:[.,]\d{1,2})?)"
    r"\s*(?:руб(?:лей)?\.?|р\.?|₽)?",
    re.IGNORECASE,
)

# Minimum / maximum reasonable fish price (₽/кг)
_MIN_PRICE = Decimal("30")
_MAX_PRICE = Decimal("15000")

# Noise words to strip from product names
_NOISE = re.compile(
    r"\b(?:опт|оптом|розница|свежий|свежая|свежемороженый|свежемороженая|"
    r"с/м|б/г|без\s*голов|п/о|потрошёный|охлаждённый|охлаждённая|"
    r"купить|продаём|продаем|наличие|доставка|склад|прайс|цена|стоимость)\b",
    re.IGNORECASE,
)


# ── LangGraph node ────────────────────────────────────────────────────────────

async def scout_node(state: AgentState) -> AgentState:
    logger.info("scout_agent: starting")
    try:
        stats = await _scan_all_groups()
        total = sum(stats.values())
        logger.info("scout_agent: done — %d new records (%s)", total, stats)
        return {**state, "worker_result": {"done": True, "records_saved": total, "by_group": stats}}
    except Exception as exc:
        logger.error("scout_agent: fatal error — %s", exc, exc_info=True)
        return {
            **state,
            "worker_result": {"done": True, "error": str(exc)},
            "errors": state["errors"] + [str(exc)],
        }


# ── Main scan loop ────────────────────────────────────────────────────────────

async def _scan_all_groups() -> dict[str, int]:
    from config import settings
    stats: dict[str, int] = {}
    for group in settings.scout_group_list:
        try:
            count = await _scan_group(group)
            stats[group] = count
        except Exception as exc:
            logger.warning("scout_agent: failed to scan %s — %s", group, exc)
            stats[group] = 0
    return stats


async def _scan_group(group: str) -> int:
    from memory.db import async_session
    from platforms.telegram_client import get_client
    from sqlalchemy import text

    client = await get_client()
    saved = 0

    async with async_session() as session:
        last_id = await _get_last_msg_id(session, group)
        logger.info("scout_agent: scanning %s from msg_id > %d", group, last_id)

        max_seen_id = last_id
        new_messages = 0

        async for message in client.iter_messages(
            group,
            min_id=last_id,
            limit=500,
            reverse=True,       # oldest first so max_seen_id grows monotonically
        ):
            if not message.text:
                max_seen_id = max(max_seen_id, message.id)
                continue

            new_messages += 1
            if message.id > max_seen_id:
                max_seen_id = message.id

            pairs = _extract_price_pairs(message.text)
            if not pairs:
                continue

            for pair in pairs:
                product_id = await _fuzzy_match_product(session, pair["product_name"])
                try:
                    await session.execute(
                        text(
                            "INSERT INTO price_intel "
                            "(source_name, source_type, raw_text, product_name, "
                            " product_id, price_rub, unit, confidence, message_id, recorded_at) "
                            "VALUES (:sn,'telegram',:raw,:pn,:pid,:pr,:unit,:conf,:mid,:ts)"
                        ),
                        {
                            "sn": group,
                            "raw": message.text[:800],
                            "pn": pair["product_name"][:200],
                            "pid": product_id,
                            "pr": pair["price_rub"],
                            "unit": pair["unit"],
                            "conf": pair["confidence"],
                            "mid": message.id,
                            "ts": datetime.now(timezone.utc),
                        },
                    )
                    saved += 1
                except Exception as exc:
                    logger.debug("scout_agent: insert failed for msg %d: %s", message.id, exc)

        if max_seen_id > last_id:
            await _save_last_msg_id(session, group, max_seen_id)

        await session.commit()
        logger.info("scout_agent: %s — %d messages, %d prices saved", group, new_messages, saved)

    return saved


# ── Progress tracking (agent_memory table) ───────────────────────────────────

async def _get_last_msg_id(session, group: str) -> int:
    from sqlalchemy import text
    key = f"scout:last_msg_id:{group}"
    row = await session.execute(
        text("SELECT value FROM agent_memory WHERE key=:k"), {"k": key}
    )
    result = row.fetchone()
    if result:
        return int(result.value.get("last_id", 0))
    return 0


async def _save_last_msg_id(session, group: str, msg_id: int) -> None:
    from sqlalchemy import text
    key = f"scout:last_msg_id:{group}"
    await session.execute(
        text(
            "INSERT INTO agent_memory (key, value) VALUES (:k, :v::jsonb) "
            "ON CONFLICT (key) DO UPDATE SET value = :v::jsonb, updated_at = NOW()"
        ),
        {"k": key, "v": f'{{"last_id": {msg_id}}}'},
    )


# ── Price extraction ──────────────────────────────────────────────────────────

def _extract_price_pairs(raw: str) -> list[dict]:
    """
    Extract (product_name, price_rub, unit, confidence) pairs from a message.

    Handles multi-line price lists, inline prices, and various Russian formats.
    """
    results: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if len(line) < 4 or len(line) > 300:
            continue

        price, unit, conf = _parse_price_from_line(line)
        if price is None:
            continue

        product = _extract_product_name(line, raw=raw)
        if not product:
            continue

        results.append({
            "product_name": product,
            "price_rub": price,
            "unit": unit,
            "confidence": conf,
        })

    return results


def _parse_price_from_line(line: str) -> tuple[Decimal | None, str, Decimal]:
    """Return (price, unit, confidence) or (None, _, _) if no price found."""
    for pattern, base_conf in [(_P1, Decimal("0.85")), (_P2, Decimal("0.80")), (_P3, Decimal("0.60"))]:
        m = pattern.search(line)
        if not m:
            continue
        try:
            price_str = m.group(1).replace(" ", "").replace(",", ".")
            price = Decimal(price_str)
        except (InvalidOperation, IndexError):
            continue

        if not (_MIN_PRICE <= price <= _MAX_PRICE):
            continue

        unit = "кг"
        if re.search(r"\bшт\b|\bупак\b|\bпак\b", line, re.IGNORECASE):
            unit = "шт"

        return price, unit, base_conf

    return None, "кг", Decimal("0")


def _extract_product_name(line: str, raw: str = "") -> str | None:
    """
    Extract the product name from a line that contains a price.
    Strategy: take text before the first price marker.
    """
    # Find where any price/currency marker starts
    price_start = len(line)
    for pattern in (_P1, _P2, _P3):
        m = pattern.search(line)
        if m and m.start() < price_start:
            price_start = m.start()

    name = line[:price_start].strip()

    # Strip bullet chars, dashes, colons at start
    name = re.sub(r"^[\s•·\-–—*►▪▸▹◦]+", "", name).strip()
    # Strip trailing separators
    name = re.sub(r"[\s\-–—:,\.]+$", "", name).strip()
    # Remove noise words
    name = _NOISE.sub("", name).strip()
    # Collapse multiple spaces
    name = re.sub(r"\s{2,}", " ", name)

    if not name or len(name) < 2 or len(name) > 150:
        return None

    # Reject lines that are purely numeric (table headers, dates)
    if re.match(r"^[\d\s\-/.,]+$", name):
        return None

    return name


# ── Product fuzzy matching ────────────────────────────────────────────────────

_product_cache: list[tuple[int, str]] | None = None   # (id, name)
_product_cache_ts: float = 0.0
_CACHE_TTL = 300.0  # seconds


async def _fuzzy_match_product(session, product_name: str) -> int | None:
    global _product_cache, _product_cache_ts
    import time
    from sqlalchemy import text

    if not product_name:
        return None

    now = time.monotonic()
    if _product_cache is None or (now - _product_cache_ts) > _CACHE_TTL:
        rows = await session.execute(
            text("SELECT id, name FROM products WHERE is_active=TRUE")
        )
        _product_cache = [(r.id, r.name) for r in rows.fetchall()]
        _product_cache_ts = now

    if not _product_cache:
        return None

    try:
        from rapidfuzz import process, fuzz

        names = [name for _, name in _product_cache]
        match = process.extractOne(
            product_name,
            names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=72,
        )
        if match:
            matched_name, score, idx = match
            product_id = _product_cache[idx][0]
            logger.debug(
                "fuzzy match: '%s' → '%s' (score=%d, id=%d)",
                product_name, matched_name, score, product_id,
            )
            return product_id
    except Exception as exc:
        logger.debug("_fuzzy_match_product error: %s", exc)
    return None
