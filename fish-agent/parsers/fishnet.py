"""
FishnetParser: цены с fishnet.ru/pricelist/russia/
Скрапит публичные прайсы поставщиков без авторизации.
Приоритет — Приморский край, потом вся Россия.
"""
import logging
import re
from decimal import Decimal, InvalidOperation

import httpx
from bs4 import BeautifulSoup

from parsers.base import BaseParser, PriceRecord

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}

BASE_URL = "https://www.fishnet.ru"
# Приморский край — основной регион поставщиков
REGION_URLS = [
    "/pricelist/russia/primorsky_krai/",
    "/pricelist/russia/sakhalin_oblast/",
    "/pricelist/russia/kamchatka_oblast/",
    "/pricelist/russia/",         # весь список если региональные пустые
]

PRICE_RE = re.compile(r"(\d[\d\s]*(?:\.\d+)?)\s*руб", re.IGNORECASE)


def _extract_price(text: str) -> Decimal | None:
    """Извлечь первое число-цену из строки."""
    text = text.strip()
    m = PRICE_RE.search(text)
    if m:
        raw = m.group(1).replace(" ", "")
        try:
            v = Decimal(raw)
            if 1 < v < 100_000:
                return v
        except InvalidOperation:
            pass
    # Fallback: ищем просто число
    nums = re.findall(r"\b(\d{2,6})\b", text)
    for n in nums:
        try:
            v = Decimal(n)
            if 50 < v < 50_000:
                return v
        except InvalidOperation:
            pass
    return None


class FishnetParser(BaseParser):
    source = "fishnet"
    url = BASE_URL + REGION_URLS[0]

    async def fetch_raw(self) -> str:
        """Собирает html со всех страниц первого рабочего региона."""
        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for path in REGION_URLS:
                url = BASE_URL + path
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.text) > 5000:
                        self.url = url
                        logger.info("fishnet: using url %s", url)
                        # Collect pages 1-3 max
                        pages = [resp.text]
                        for page_num in range(2, 4):
                            pr = await client.get(f"{url}?page={page_num}")
                            if pr.status_code == 200:
                                pages.append(pr.text)
                        return "\n".join(pages)
                except Exception as e:
                    logger.warning("fishnet: %s failed: %s", path, e)
        return ""

    def parse_raw(self, raw: str) -> list[PriceRecord]:
        soup = BeautifulSoup(raw, "lxml")
        records: list[PriceRecord] = []

        # fishnet.ru uses div.b-pricelist__item or similar for each price listing
        # Try multiple known class patterns
        items = (
            soup.select(".b-pricelist__item")
            or soup.select(".pricelist-item")
            or soup.select(".price-item")
            or soup.select("tr.pricelist")
            or soup.select(".catalog-item")
        )

        if not items:
            # Generic fallback: look for table rows with price-like content
            items = soup.select("table tr")

        for item in items:
            text = item.get_text(separator="|", strip=True)
            if not text or len(text) < 10:
                continue

            # Extract product name: first meaningful text piece
            # Try to find dedicated name cells first
            name_el = (
                item.select_one(".b-pricelist__name")
                or item.select_one(".pricelist-name")
                or item.select_one(".product-name")
                or item.select_one("td:first-child")
                or item.select_one("a")
            )
            name = name_el.get_text(strip=True) if name_el else text.split("|")[0]

            # Skip non-product rows
            if not name or len(name) > 200 or name.lower().startswith("наименование"):
                continue

            # Price
            price_el = (
                item.select_one(".b-pricelist__price")
                or item.select_one(".price-opt")
                or item.select_one(".price")
                or item.select_one("td:nth-child(2)")
            )
            price_text = price_el.get_text(strip=True) if price_el else ""
            # Also search the full text for a price
            price = _extract_price(price_text) or _extract_price(text)

            if price is None:
                continue  # Skip entries without visible price

            # Company / supplier
            company_el = (
                item.select_one(".b-pricelist__saler")
                or item.select_one(".company-name")
                or item.select_one(".saler")
                or item.select_one("td:nth-child(4)")
            )
            company = company_el.get_text(strip=True) if company_el else ""

            # City
            city_el = item.select_one(".city") or item.select_one("td:nth-child(5)")
            city = city_el.get_text(strip=True) if city_el else ""

            # Append city to company for context
            supplier_name = f"{company} ({city})" if company and city else (company or None)
            records.append(
                PriceRecord(
                    raw_name=name,
                    price_rub=price,
                    source=self.source,
                    source_url=self.url,
                    supplier_name=supplier_name,
                )
            )

        logger.info("fishnet.ru: parsed %d records from %s", len(records), self.url)
        return records
