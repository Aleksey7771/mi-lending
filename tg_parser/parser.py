"""
Парсер цен из Telegram-групп по рыбопродукции.
Требует: pip install telethon openpyxl

Настройка:
  1. Зайди на https://my.telegram.org → API development tools
  2. Создай приложение, скопируй api_id и api_hash
  3. Добавь в fish-agent/.env:
       TG_API_ID=12345678
       TG_API_HASH=abc123...
  4. Запуск: python tg_parser/parser.py
"""

import asyncio
import re
import csv
import os
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import Message

# Загружаем .env из fish-agent/
_env_path = Path(__file__).parent.parent / "fish-agent" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

# ─── НАСТРОЙКИ ───────────────────────────────────────────────
API_ID   = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH", "")

# Группы для мониторинга
_groups_env = os.getenv("TG_GROUPS", "rybabaza,sebreez,fishretailtrade,moriki_vdk")
GROUPS = [g.strip() for g in _groups_env.split(",") if g.strip()]

# Сколько последних сообщений читать из каждой группы
MESSAGES_LIMIT = 200

# Файл для сохранения результатов
OUTPUT_FILE = "prices.csv"
# ─────────────────────────────────────────────────────────────

# Паттерны для поиска цен
PRICE_PATTERNS = [
    r'\d[\d\s]*(?:руб|₽|rub)(?:[./]кг|/kg)?',
    r'цена[:\s]+\d+',
    r'прайс',
    r'\d+\s*(?:руб|₽)[^а-яА-Я]',
    r'от\s+\d+\s*(?:руб|₽)',
]

# Ключевые слова рыбной тематики
FISH_KEYWORDS = [
    'треска', 'лосось', 'горбуша', 'кета', 'нерка', 'семга', 'форель',
    'минтай', 'палтус', 'камбала', 'терпуг', 'навага', 'сельдь',
    'скумбрия', 'тунец', 'хек', 'пикша', 'судак', 'щука',
    'краб', 'креветка', 'кальмар', 'осьминог', 'мидия', 'устрица',
    'икра', 'морепродукт', 'рыба', 'филе', 'б/г', 'пбг', 'нр',
    'мороженый', 'свежемороженый', 'охлаждённый',
]

COMPILED_PRICE = [re.compile(p, re.IGNORECASE) for p in PRICE_PATTERNS]
COMPILED_FISH  = [re.compile(k, re.IGNORECASE) for k in FISH_KEYWORDS]


def has_price(text: str) -> bool:
    return any(p.search(text) for p in COMPILED_PRICE)


def has_fish(text: str) -> bool:
    return any(k.search(text) for k in COMPILED_FISH)


def extract_prices(text: str) -> list[str]:
    found = []
    for p in COMPILED_PRICE:
        found += p.findall(text)
    return list(set(found))


async def parse_group(client: TelegramClient, group: str) -> list[dict]:
    results = []
    print(f"\n📥 Читаю группу @{group}...")

    try:
        entity = await client.get_entity(group)
        async for msg in client.iter_messages(entity, limit=MESSAGES_LIMIT):
            if not isinstance(msg, Message) or not msg.text:
                continue

            text = msg.text.strip()
            if not text:
                continue

            # Берём только сообщения с ценами И рыбной тематикой
            if has_price(text) and has_fish(text):
                results.append({
                    "группа":    f"@{group}",
                    "дата":      msg.date.strftime("%Y-%m-%d %H:%M"),
                    "автор_id":  str(msg.sender_id or ""),
                    "цены":      ", ".join(extract_prices(text)),
                    "текст":     text[:500].replace("\n", " "),
                    "ссылка":    f"https://t.me/{group}/{msg.id}",
                })

        print(f"   ✅ Найдено {len(results)} сообщений с ценами")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    return results


def save_csv(rows: list[dict], filepath: str):
    if not rows:
        print("\n⚠️  Нет данных для сохранения.")
        return

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n💾 Сохранено {len(rows)} строк → {filepath}")


async def main():
    if not API_ID or not API_HASH:
        print("❌ Укажи API_ID и API_HASH в начале файла parser.py")
        return

    print("🚀 Запуск парсера рыбных Telegram-групп")
    print(f"   Группы: {', '.join(GROUPS)}")
    print(f"   Сообщений на группу: {MESSAGES_LIMIT}")

    client = TelegramClient("fish_session", API_ID, API_HASH)

    async with client:
        await client.start()
        print("\n✅ Telegram авторизован")

        all_rows = []
        for group in GROUPS:
            rows = await parse_group(client, group)
            all_rows.extend(rows)

        save_csv(all_rows, OUTPUT_FILE)

        # Сводка по группам
        print("\n📊 Сводка:")
        for group in GROUPS:
            count = sum(1 for r in all_rows if r["группа"] == f"@{group}")
            print(f"   @{group}: {count} сообщений с ценами")

        print(f"\n✅ Готово! Открой файл: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
