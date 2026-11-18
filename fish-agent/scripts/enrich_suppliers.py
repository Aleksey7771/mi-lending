"""
Автоматическое обогащение поставщиков контактами с fishnet.ru.

Алгоритм:
  1. Скачать каталог fishnet.ru/catalog/russia/ (все страницы)
     → получить словарь  название -> URL компании
  2. Для каждого поставщика без телефона найти его URL в каталоге
  3. Открыть страницу контактов (/slug/?dmode=contacts)
  4. Вытащить: Телефон, Email, Сайт
  5. Сохранить в БД

Запуск вручную:
  .venv\\Scripts\\python.exe scripts/enrich_suppliers.py [--limit N]

Автозапуск: планировщик, 03:00 Владивосток, по 50 компаний в день.
"""

import asyncio
import logging
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE = "https://www.fishnet.ru"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# Каталог компаний fishnet.ru — правильные пути
CATALOG_PATHS = [
    "/companies/russia/",          # весь список России
    "/companies/russia/dfo/",      # Дальневосточный ФО (наш основной регион)
    "/companies/russia/cfo/",      # ЦФО
    "/companies/russia/szfo/",     # Северо-Западный ФО
    "/companies/russia/sfo/",      # Сибирский ФО
]


def _normalize(name: str) -> str:
    """Привести к нижнему регистру без лишних пробелов/знаков для сравнения."""
    name = name.lower().strip()
    name = re.sub(r"[,.\-«»\"']", " ", name)
    name = re.sub(r"\s+", " ", name)
    # убрать правовую форму
    name = re.sub(r"\b(ооо|оао|зао|ао|ип|пао|фгбу|фгуп|гуп)\b", "", name)
    return name.strip()


async def build_catalog(client: httpx.AsyncClient) -> dict[str, str]:
    """
    Обходит каталог fishnet.ru и строит словарь:
      normalized_name -> company_url
    """
    catalog: dict[str, str] = {}

    for path in CATALOG_PATHS:
        for page in range(1, 20):  # максимум 19 страниц
            url = BASE + path + (f"?page={page}" if page > 1 else "")
            try:
                resp = await client.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "lxml")

                # Правильные классы fishnet.ru (проверено)
                items = soup.select(".company_item")

                found = 0
                for item in items:
                    link = item.select_one(".company_title_link, a.company_title_link, h2 a, h3 a")
                    if not link:
                        link = item.select_one("a[href]")
                    if not link:
                        continue
                    href = link.get("href", "")
                    if not href or href in ("/", "/companies/"):
                        continue
                    name = link.get_text(strip=True)
                    if not name or len(name) < 3:
                        continue
                    company_url = BASE + href if href.startswith("/") else href
                    catalog[_normalize(name)] = company_url
                    found += 1

                logger.debug("catalog %s page %d: %d компаний", path, page, found)

                # Если нет кнопки "следующая страница" — выходим
                if not soup.select_one("a[rel='next'], .pagination__next, a.next"):
                    break

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.debug("catalog error %s p%d: %s", path, page, e)
                break

    logger.info("Каталог fishnet.ru: %d компаний найдено", len(catalog))
    return catalog


async def scrape_contacts(client: httpx.AsyncClient, company_url: str) -> dict:
    """
    Открывает страницу контактов компании и извлекает телефон/email/сайт.
    URL контактов: company_url + '?dmode=contacts'  (или ищем ссылку на вкладку)
    """
    contacts_url = company_url.rstrip("/") + "/?dmode=contacts"
    try:
        resp = await client.get(contacts_url, headers=HEADERS, timeout=12, follow_redirects=True)
        if resp.status_code != 200:
            # Попробуем найти ссылку "КОНТАКТЫ" на основной странице
            main = await client.get(company_url, headers=HEADERS, timeout=12, follow_redirects=True)
            soup0 = BeautifulSoup(main.text, "lxml")
            tab = soup0.find("a", string=re.compile(r"контакт", re.I))
            if tab and tab.get("href"):
                href = tab["href"]
                contacts_url = BASE + href if href.startswith("/") else href
                resp = await client.get(contacts_url, headers=HEADERS, timeout=12, follow_redirects=True)
                if resp.status_code != 200:
                    return {}
            else:
                return {}

        soup = BeautifulSoup(resp.text, "lxml")
        result = {}

        # ── Телефон ──────────────────────────────────────────────
        # Вариант 1: <a href="tel:...">
        tel_link = soup.select_one("a[href^='tel:']")
        if tel_link:
            result["phone"] = tel_link.get_text(strip=True)
        else:
            # Вариант 2: текст после метки "Телефон:"
            for tag in soup.find_all(string=re.compile(r"Телефон", re.I)):
                parent = tag.parent
                text = parent.get_text(separator="\n", strip=True)
                phones = re.findall(r"\+?[78][\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}", text)
                if phones:
                    result["phone"] = phones[0]
                    break

        # ── Email ────────────────────────────────────────────────
        email_link = soup.select_one("a[href^='mailto:']")
        if email_link:
            result["email"] = email_link["href"].replace("mailto:", "").strip()

        # ── Сайт ─────────────────────────────────────────────────
        for a in soup.select("a[href^='http']"):
            href = a["href"]
            if "fishnet.ru" not in href and len(href) < 200:
                result["website"] = href
                break

        return result

    except Exception as e:
        logger.debug("contacts error %s: %s", company_url, e)
        return {}


def find_company_url(catalog: dict[str, str], name: str) -> str | None:
    """Нечёткий поиск компании по имени в каталоге."""
    norm = _normalize(name)
    # 1. Точное совпадение
    if norm in catalog:
        return catalog[norm]
    # 2. Частичное — ищем как подстроку
    for cat_name, url in catalog.items():
        if norm in cat_name or cat_name in norm:
            return url
    # 3. Первые 3 слова названия
    words = norm.split()[:3]
    if len(words) >= 2:
        prefix = " ".join(words)
        for cat_name, url in catalog.items():
            if prefix in cat_name:
                return url
    return None


async def run_enrichment(limit: int = 0) -> int:
    from sqlalchemy import select
    from memory.db import AsyncSessionFactory
    from memory.models import Supplier

    # Загрузить поставщиков без телефона
    async with AsyncSessionFactory() as session:
        q = select(Supplier).where(
            Supplier.is_active == True,
            Supplier.phone.is_(None),
        ).order_by(Supplier.id)
        if limit:
            q = q.limit(limit)
        rows = (await session.execute(q)).scalars().all()

    total = len(rows)
    logger.info("Поставщиков без телефона: %d", total)
    if not total:
        return 0

    phones_added = 0
    emails_added = 0

    async with httpx.AsyncClient() as http:
        # Строим каталог один раз
        logger.info("Скачиваю каталог fishnet.ru...")
        catalog = await build_catalog(http)

        if not catalog:
            logger.warning("Каталог пуст — возможно, структура сайта изменилась.")

        async with AsyncSessionFactory() as session:
            for i, sup in enumerate(rows, 1):
                company_url = find_company_url(catalog, sup.name)
                if not company_url:
                    logger.debug("[%d/%d] не найден в каталоге: %s", i, total, sup.name)
                    continue

                logger.info("[%d/%d] %s → %s", i, total, sup.name, company_url)
                data = await scrape_contacts(http, company_url)

                if not data.get("phone") and not data.get("email"):
                    logger.debug("  контактов нет")
                    await asyncio.sleep(0.8)
                    continue

                refreshed = await session.get(Supplier, sup.id)
                if refreshed:
                    if data.get("phone") and not refreshed.phone:
                        refreshed.phone = data["phone"]
                        phones_added += 1
                        logger.info("  📞 %s", data["phone"])
                    if data.get("email") and not refreshed.email:
                        refreshed.email = data["email"]
                        emails_added += 1
                        logger.info("  📧 %s", data["email"])
                    if data.get("website") and not refreshed.notes:
                        refreshed.notes = data["website"]

                await session.commit()
                await asyncio.sleep(1.0)

    logger.info(
        "Готово. Телефонов: +%d, Email: +%d (из %d компаний)",
        phones_added, emails_added, total,
    )
    return phones_added


async def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    await run_enrichment(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
