import logging

import httpx
from bs4 import BeautifulSoup

from parsers.base import BaseParser, PriceRecord
from parsers.normalizer import normalize_price

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class FishretailParser(BaseParser):
    source = "fishretail"
    url = "https://fishretail.ru/trade/list/"

    async def fetch_raw(self) -> str:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
            return resp.text

    def parse_raw(self, raw: str) -> list[PriceRecord]:
        soup = BeautifulSoup(raw, "lxml")
        records: list[PriceRecord] = []

        # fishretail.ru trade listings: items with product name + price
        items = soup.select(".trade-item, .product-item, .lot-item")
        if not items:
            items = soup.select("article, .item")

        for item in items:
            name_el = item.select_one(".trade-name, .product-name, h3, h2, .title")
            price_el = item.select_one(".trade-price, .price, .cost")
            company_el = item.select_one(".company-name, .seller, .vendor")

            if not name_el or not price_el:
                continue

            name = name_el.get_text(strip=True)
            price = normalize_price(price_el.get_text(strip=True))

            if not name or price is None or price <= 0:
                continue

            company = company_el.get_text(strip=True) if company_el else None
            records.append(
                PriceRecord(
                    raw_name=name,
                    price_rub=price,
                    source=self.source,
                    source_url=self.url,
                    supplier_name=company,
                )
            )

        logger.info("fishretail.ru: parsed %d records", len(records))
        return records
