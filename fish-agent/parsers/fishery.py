"""
FisheryParser: цены с fishery.ru
Поддерживает:
  1. HTML-таблицу цен на сайте
  2. Скачивание Excel-прайсов по ссылкам
  3. Claude-экстракцию из нестандартных файлов
"""
import asyncio
import io
import logging
import re
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

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
    "Referer": "https://www.fishery.ru/",
}

BASE_URL = "https://www.fishery.ru"
PRICE_URLS = [
    "/news/prices/",
    "/prices/",
    "/price/",
    "/market/prices/",
]

PRICE_RE = re.compile(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(?:руб|₽|р\.)", re.IGNORECASE)
NUM_RE = re.compile(r"\b(\d{2,6}(?:[.,]\d+)?)\b")

# Keywords for fish products
FISH_KEYWORDS = re.compile(
    r"(треска|лосось|горбуша|минтай|навага|камбала|палтус|сельдь|кета|нерка"
    r"|чавыча|форель|семга|судак|щука|сом|карп|морепродукт|краб|креветк|икра"
    r"|гребешок|мидия|кальмар|осьминог|морской ёж|ламинария|морская капуст)",
    re.IGNORECASE,
)


def _parse_price(text: str) -> Decimal | None:
    text = text.strip().replace(",", ".")
    m = PRICE_RE.search(text)
    if m:
        raw = m.group(1).replace(" ", "").replace(",", ".")
        try:
            v = Decimal(raw)
            if 20 < v < 200_000:
                return v
        except InvalidOperation:
            pass
    nums = NUM_RE.findall(text)
    for n in nums:
        try:
            v = Decimal(n.replace(",", "."))
            if 50 < v < 50_000:
                return v
        except InvalidOperation:
            pass
    return None


def _extract_rows_from_html(html: str, source_url: str) -> list[PriceRecord]:
    soup = BeautifulSoup(html, "lxml")
    records: list[PriceRecord] = []

    # Try price tables
    for table in soup.select("table"):
        headers_row = table.select_one("tr")
        if not headers_row:
            continue
        headers = [th.get_text(strip=True).lower() for th in headers_row.select("th, td")]

        # Detect column positions
        name_col = next((i for i, h in enumerate(headers) if any(k in h for k in ("наим", "продукт", "товар", "рыба"))), 0)
        price_col = next((i for i, h in enumerate(headers) if any(k in h for k in ("цена", "стоим", "руб", "₽"))), 1)
        supplier_col = next((i for i, h in enumerate(headers) if any(k in h for k in ("поставщ", "компани", "продав", "фирм"))), None)

        for row in table.select("tr")[1:]:
            cells = row.select("td")
            if len(cells) < 2:
                continue
            name = cells[name_col].get_text(strip=True) if name_col < len(cells) else ""
            price_text = cells[price_col].get_text(strip=True) if price_col < len(cells) else ""
            supplier = ""
            if supplier_col is not None and supplier_col < len(cells):
                supplier = cells[supplier_col].get_text(strip=True)

            if not name or not FISH_KEYWORDS.search(name):
                continue
            price = _parse_price(price_text)
            if not price:
                # Try to find price in full row text
                price = _parse_price(row.get_text(strip=True))
            if not price:
                continue

            records.append(PriceRecord(
                raw_name=name[:200],
                price_rub=price,
                source="fishery",
                source_url=source_url,
                supplier_name=supplier[:100] if supplier else None,
            ))

    # Also check div-based price blocks
    for block in soup.select(".price-row, .fish-price, .market-price, .price-item, [class*='price']"):
        text = block.get_text(separator=" | ", strip=True)
        if not FISH_KEYWORDS.search(text):
            continue
        price = _parse_price(text)
        if not price:
            continue
        # Name = first segment before price
        name = text.split("|")[0].strip()[:200]
        if len(name) < 3:
            continue
        records.append(PriceRecord(
            raw_name=name,
            price_rub=price,
            source="fishery",
            source_url=source_url,
        ))

    return records


def _extract_from_xlsx(data: bytes, source_url: str) -> list[PriceRecord]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        records = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(c).strip() if c is not None else "" for c in row]
                if not any(cells):
                    continue
                # Find fish name and price in row
                name = ""
                price = None
                for cell in cells:
                    if FISH_KEYWORDS.search(cell) and len(cell) > 3:
                        name = cell[:200]
                    p = _parse_price(cell)
                    if p and price is None:
                        price = p
                if name and price:
                    records.append(PriceRecord(
                        raw_name=name,
                        price_rub=price,
                        source="fishery_xlsx",
                        source_url=source_url,
                    ))
        logger.info("fishery xlsx: %d records", len(records))
        return records
    except Exception as e:
        logger.warning("fishery xlsx parse error: %s", e)
        return []


def _extract_from_pdf(data: bytes, source_url: str) -> list[PriceRecord]:
    try:
        import pdfplumber
        records = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages[:10]:  # max 10 pages
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        cells = [str(c).strip() if c else "" for c in row]
                        name = ""
                        price = None
                        for cell in cells:
                            if FISH_KEYWORDS.search(cell) and len(cell) > 3 and not name:
                                name = cell[:200]
                            p = _parse_price(cell)
                            if p and price is None:
                                price = p
                        if name and price:
                            records.append(PriceRecord(
                                raw_name=name,
                                price_rub=price,
                                source="fishery_pdf",
                                source_url=source_url,
                            ))
                # Fallback: raw text if no table found
                if not tables:
                    text = page.extract_text() or ""
                    for line in text.split("\n"):
                        if not FISH_KEYWORDS.search(line):
                            continue
                        price = _parse_price(line)
                        if price:
                            name = re.sub(r"\d[\d\s.,]*(?:руб|₽|р\.)?.*", "", line).strip()
                            if len(name) > 3:
                                records.append(PriceRecord(
                                    raw_name=name[:200],
                                    price_rub=price,
                                    source="fishery_pdf",
                                    source_url=source_url,
                                ))
        logger.info("fishery pdf: %d records", len(records))
        return records
    except Exception as e:
        logger.warning("fishery pdf parse error: %s", e)
        return []


async def _llm_extract(text: str, source_url: str) -> list[PriceRecord]:
    """Use Claude to extract prices from unstructured text (last resort)."""
    if len(text) > 8000:
        text = text[:8000]
    try:
        from openai import AsyncOpenAI
        from config import settings
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": (
                    "Извлеки из текста строки с ценами на рыбу и морепродукты. "
                    "Верни ТОЛЬКО JSON-список: "
                    '[{"name": "треска б/г", "price": 182, "supplier": "Иванов"}, ...]'
                    "Если ничего нет — верни пустой список []."
                )},
                {"role": "user", "content": text},
            ],
        )
        raw = response.choices[0].message.content.strip()
        import json
        # Find JSON array in response
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        data = json.loads(match.group(0))
        records = []
        for item in data:
            try:
                price = Decimal(str(item.get("price", 0)))
                name = str(item.get("name", "")).strip()
                if name and 20 < price < 200_000:
                    records.append(PriceRecord(
                        raw_name=name[:200],
                        price_rub=price,
                        source="fishery_llm",
                        source_url=source_url,
                        supplier_name=str(item.get("supplier", ""))[:100] or None,
                    ))
            except (InvalidOperation, KeyError):
                pass
        logger.info("fishery llm: %d records extracted", len(records))
        return records
    except Exception as e:
        logger.warning("fishery llm extract error: %s", e)
        return []


class FisheryParser(BaseParser):
    source = "fishery"
    url = BASE_URL + PRICE_URLS[0]

    async def fetch_raw(self) -> str:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for path in PRICE_URLS:
                url = BASE_URL + path
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.text) > 2000:
                        self.url = url
                        logger.info("fishery: found prices at %s", url)
                        return resp.text
                except Exception as e:
                    logger.debug("fishery: %s → %s", path, e)
        logger.warning("fishery: no price page found")
        return ""

    def parse_raw(self, raw: str) -> list[PriceRecord]:
        # This method is called synchronously — use extract_from_html
        return _extract_rows_from_html(raw, self.url)

    async def parse(self) -> list[PriceRecord]:
        """Full async parse: HTML + file downloads + LLM fallback."""
        records: list[PriceRecord] = []

        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            # 1. Find the right price page
            html = ""
            for path in PRICE_URLS:
                url = BASE_URL + path
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.text) > 2000:
                        self.url = url
                        html = resp.text
                        logger.info("fishery: price page found at %s (%d bytes)", url, len(html))
                        break
                except Exception as e:
                    logger.debug("fishery probe %s: %s", path, e)

            if not html:
                logger.warning("fishery: cannot reach price page — skipping")
                return []

            # 2. Extract from HTML tables
            html_records = _extract_rows_from_html(html, self.url)
            records.extend(html_records)
            logger.info("fishery html: %d records", len(html_records))

            # 3. Find downloadable price files (.xlsx, .xls, .pdf)
            soup = BeautifulSoup(html, "lxml")
            file_links = []
            for a in soup.select("a[href]"):
                href = a["href"]
                if any(href.lower().endswith(ext) for ext in (".xlsx", ".xls", ".pdf")):
                    full = href if href.startswith("http") else BASE_URL + href
                    file_links.append(full)

            file_links = list(dict.fromkeys(file_links))[:10]  # deduplicate, max 10 files
            logger.info("fishery: found %d price files", len(file_links))

            for file_url in file_links:
                try:
                    resp = await client.get(file_url, timeout=20)
                    if resp.status_code != 200:
                        continue
                    data = resp.content
                    ext = file_url.lower().rsplit(".", 1)[-1]
                    if ext in ("xlsx", "xls"):
                        file_records = _extract_from_xlsx(data, file_url)
                    elif ext == "pdf":
                        file_records = _extract_from_pdf(data, file_url)
                    else:
                        continue
                    records.extend(file_records)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.debug("fishery file %s: %s", file_url, e)

            # 4. LLM fallback if still no records
            if not records:
                logger.info("fishery: no structured data found, trying LLM extraction")
                text = soup.get_text(separator="\n", strip=True)
                llm_records = await _llm_extract(text, self.url)
                records.extend(llm_records)

        logger.info("fishery total: %d records", len(records))
        return records
