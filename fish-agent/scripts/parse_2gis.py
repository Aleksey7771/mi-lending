"""
Парсер 2ГИС для сбора потенциальных клиентов (рестораны, рыбные магазины, оптовики).
Результаты импортируются в таблицу clients.

Регистрация API ключа (бесплатно):
  https://dev.2gis.com/

Запуск:
  python scripts/parse_2gis.py --city vladivostok --key <YOUR_API_KEY>
  python scripts/parse_2gis.py --city novosibirsk --key <YOUR_API_KEY>

Без ключа — сохраняет результаты только в CSV (clients_2gis.csv).
"""
import argparse
import asyncio
import csv
import logging
import os
import sys
from pathlib import Path

import httpx

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ─── Настройки ────────────────────────────────────────────────
CATEGORIES = [
    "рыбный ресторан",
    "рыбный магазин",
    "рыба опт",
    "морепродукты",
    "суши-бар",
    "японский ресторан",
    "рыбоперерабатывающий завод",
]

CITY_COORDS = {
    "vladivostok":  "131.9,43.1",
    "novosibirsk":  "82.9,55.0",
    "moscow":       "37.6,55.75",
    "saint_petersburg": "30.3,59.9",
    "khabarovsk":   "135.1,48.5",
    "yuzhno_sakhalinsk": "142.7,46.9",
}

API_BASE = "https://catalog.api.2gis.com/3.0/items"
OUTPUT_CSV = Path(__file__).parent.parent / "data" / "clients_2gis.csv"
# ──────────────────────────────────────────────────────────────


async def search_2gis(
    client: httpx.AsyncClient, query: str, location: str, api_key: str, page: int = 1
) -> list[dict]:
    """Один запрос к API 2ГИС."""
    params = {
        "q": query,
        "location": location,
        "page": page,
        "pagesize": 50,
        "fields": "items.contact_groups,items.full_address_name,items.rubrics,items.name_ex",
        "key": api_key,
    }
    try:
        resp = await client.get(API_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("items", [])
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.error("API key неверный или превышен лимит запросов")
        else:
            logger.warning("2GIS API error %s for query '%s'", e.response.status_code, query)
        return []
    except Exception as e:
        logger.warning("2GIS error: %s", e)
        return []


def extract_phone(item: dict) -> str:
    """Достать первый телефон из contact_groups."""
    for group in item.get("contact_groups", []):
        for c in group.get("contacts", []):
            if c.get("type") == "phone":
                return c.get("value", "")
    return ""


def extract_category(item: dict) -> str:
    """Категория бизнеса из rubrics."""
    rubrics = item.get("rubrics", [])
    if rubrics:
        return rubrics[0].get("name", "")
    return ""


async def collect_clients(city: str, api_key: str) -> list[dict]:
    """Собрать всех клиентов по всем категориям в указанном городе."""
    location = CITY_COORDS.get(city, "131.9,43.1")
    all_clients: dict[str, dict] = {}  # deduplicate by name+address

    async with httpx.AsyncClient() as client:
        for query in CATEGORIES:
            logger.info("Поиск: '%s' в %s ...", query, city)
            for page in range(1, 4):  # первые 3 страницы = 150 результатов
                items = await search_2gis(client, query, location, api_key, page)
                if not items:
                    break
                for item in items:
                    name = item.get("name", "").strip()
                    address = item.get("full_address_name", "").strip()
                    phone = extract_phone(item)
                    category = extract_category(item)
                    key = f"{name}|{address}"
                    item_id = item.get("id", "")
                    url_city = city.replace("_", "-")
                    gis_url = f"https://2gis.ru/{url_city}/firm/{item_id}" if item_id else ""
                    if key not in all_clients:
                        all_clients[key] = {
                            "name": name,
                            "type": category or query,
                            "city": city.replace("_", " ").title(),
                            "address": address,
                            "phone": phone,
                            "url_2gis": gis_url,
                            "source": "2gis",
                            "status": "не звонили",
                        }
                await asyncio.sleep(0.3)  # Задержка между запросами

    return list(all_clients.values())


def save_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Сохранено %d клиентов → %s", len(rows), path)


async def import_to_db(rows: list[dict]) -> int:
    """Импортировать в PostgreSQL, пропуская дубликаты по имени."""
    from memory.db import AsyncSessionFactory
    from memory.models import Client
    from sqlalchemy import select

    added = 0
    async with AsyncSessionFactory() as session:
        for row in rows:
            existing = (await session.execute(
                select(Client).where(Client.name == row["name"])
            )).scalar_one_or_none()
            if existing:
                continue
            c = Client(
                name=row["name"][:100],
                type=(row.get("type") or "")[:50] or None,
                city=row.get("city") or None,
                phone=row.get("phone") or None,
                address=row.get("address") or None,
                notes=f"Категория: {row.get('type', '')}",
                source="2gis",
                lead_status="new",
            )
            session.add(c)
            added += 1
        await session.commit()
    return added


async def main():
    parser = argparse.ArgumentParser(description="2ГИС парсер клиентов для рыбного опта")
    parser.add_argument("--city", default="vladivostok",
                        choices=list(CITY_COORDS.keys()),
                        help="Город для поиска")
    parser.add_argument("--key", default=os.getenv("TWOGIS_API_KEY", ""),
                        help="API ключ 2ГИС (или env TWOGIS_API_KEY)")
    parser.add_argument("--csv-only", action="store_true",
                        help="Только CSV, без импорта в БД")
    args = parser.parse_args()

    if not args.key:
        print(
            "\n❌ Нужен API ключ 2ГИС.\n"
            "Получи бесплатно: https://dev.2gis.com/\n"
            "Запуск: python scripts/parse_2gis.py --city vladivostok --key <KEY>\n"
            "Или установи: $env:TWOGIS_API_KEY='<KEY>'"
        )
        sys.exit(1)

    logger.info("Парсинг 2ГИС: город=%s", args.city)
    rows = await collect_clients(args.city, args.key)

    if not rows:
        logger.warning("Нет результатов. Проверь API ключ и подключение.")
        sys.exit(0)

    logger.info("Найдено %d уникальных компаний", len(rows))
    save_csv(rows, OUTPUT_CSV)

    if not args.csv_only:
        try:
            added = await import_to_db(rows)
            logger.info("Добавлено в БД: %d (дублей пропущено: %d)", added, len(rows) - added)
        except Exception as e:
            logger.error("Ошибка импорта в БД: %s", e)
            logger.info("Данные сохранены в CSV: %s", OUTPUT_CSV)
    else:
        logger.info("Режим --csv-only: БД не обновлялась. Файл: %s", OUTPUT_CSV)


if __name__ == "__main__":
    asyncio.run(main())
