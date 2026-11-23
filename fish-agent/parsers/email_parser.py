"""
EmailParser: читает входящие письма через IMAP, извлекает прайсы из вложений.

Алгоритм:
  1. Подключиться к IMAP (Mail.ru, imap.mail.ru:993)
  2. Найти непрочитанные письма с вложениями (.xlsx/.xls/.pdf)
  3. Скачать вложения
  4. Извлечь цены через openpyxl / pdfplumber / Claude
  5. Вернуть список PriceRecord + мета-информацию об отправителе
  6. Пометить письмо как прочитанное
"""
import asyncio
import email
import imaplib
import io
import logging
import re
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from email.header import decode_header
from email.message import Message

from config import settings
from parsers.base import PriceRecord

logger = logging.getLogger(__name__)

# Ключевые слова, по которым считаем письмо связанным с ценами
PRICE_SUBJECT_RE = re.compile(
    r"(прайс|цен|price|рыб|рыб|морепродукт|fish|seafood|стоимост|предложен|прайслист)",
    re.IGNORECASE,
)

# Ключевые слова для автоответа (клиент просит прайс)
REQUEST_SUBJECT_RE = re.compile(
    r"(пришлите|пришли|хочу|нужен|запрос|request|прайс|price list|прайслист)",
    re.IGNORECASE,
)

FISH_RE = re.compile(
    r"(треска|лосось|горбуша|минтай|навага|камбала|палтус|сельдь|кета|нерка"
    r"|чавыча|форель|семга|судак|щука|сом|карп|морепродукт|краб|креветк|икра"
    r"|гребешок|мидия|кальмар|осьминог)",
    re.IGNORECASE,
)

PRICE_NUM_RE = re.compile(r"\b(\d{2,6}(?:[.,]\d+)?)\b")


@dataclass
class EmailMessage:
    uid: bytes
    subject: str
    sender: str
    sender_email: str
    date: str
    body: str
    attachments: list[dict] = field(default_factory=list)
    # attachments: [{"filename": str, "data": bytes, "content_type": str}]


def _decode_str(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    parts = decode_header(value)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _fetch_emails_sync(max_count: int = 20) -> list[EmailMessage]:
    """Synchronous IMAP fetch — runs in thread."""
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("IMAP: credentials not set, skipping")
        return []

    ctx = ssl.create_default_context()
    messages = []

    try:
        with imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port, ssl_context=ctx) as imap:
            imap.login(settings.smtp_user, settings.smtp_password)
            imap.select("INBOX")

            # Search unseen messages
            status, uids_raw = imap.search(None, "UNSEEN")
            if status != "OK":
                return []

            uids = uids_raw[0].split()
            if not uids:
                logger.info("IMAP: no unseen messages")
                return []

            # Process newest first, limit
            uids = uids[-max_count:]
            logger.info("IMAP: %d unseen messages to check", len(uids))

            for uid in uids:
                try:
                    status, data = imap.fetch(uid, "(RFC822)")
                    if status != "OK" or not data or not data[0]:
                        continue

                    raw = data[0][1] if isinstance(data[0], tuple) else data[0]
                    msg: Message = email.message_from_bytes(raw)

                    subject = _decode_str(msg.get("Subject", ""))
                    sender_full = _decode_str(msg.get("From", ""))
                    date_str = msg.get("Date", "")

                    # Extract email address
                    sender_email = ""
                    m = re.search(r"<([^>]+)>", sender_full)
                    sender_email = m.group(1).lower() if m else sender_full.lower().strip()
                    sender_name = re.sub(r"<[^>]+>", "", sender_full).strip().strip('"')

                    # Extract body and attachments
                    body = ""
                    attachments = []

                    if msg.is_multipart():
                        for part in msg.walk():
                            ct = part.get_content_type()
                            cd = part.get("Content-Disposition", "")

                            if ct == "text/plain" and "attachment" not in cd:
                                payload = part.get_payload(decode=True)
                                charset = part.get_content_charset() or "utf-8"
                                if payload:
                                    body += payload.decode(charset, errors="replace")

                            elif "attachment" in cd or part.get_filename():
                                filename = _decode_str(part.get_filename() or "")
                                if any(filename.lower().endswith(ext) for ext in
                                       (".xlsx", ".xls", ".pdf", ".csv")):
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        attachments.append({
                                            "filename": filename,
                                            "data": payload,
                                            "content_type": ct,
                                        })
                    else:
                        payload = msg.get_payload(decode=True)
                        charset = msg.get_content_charset() or "utf-8"
                        if payload:
                            body = payload.decode(charset, errors="replace")

                    messages.append(EmailMessage(
                        uid=uid,
                        subject=subject,
                        sender=sender_name,
                        sender_email=sender_email,
                        date=date_str,
                        body=body[:3000],
                        attachments=attachments,
                    ))

                except Exception as e:
                    logger.warning("IMAP: error parsing message %s: %s", uid, e)

    except imaplib.IMAP4.error as e:
        logger.error("IMAP login/connect failed: %s", e)
    except Exception as e:
        logger.error("IMAP unexpected error: %s", e)

    return messages


def _mark_seen_sync(uids: list[bytes]) -> None:
    """Mark messages as read."""
    if not uids or not settings.smtp_user or not settings.smtp_password:
        return
    ctx = ssl.create_default_context()
    try:
        with imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port, ssl_context=ctx) as imap:
            imap.login(settings.smtp_user, settings.smtp_password)
            imap.select("INBOX")
            for uid in uids:
                imap.store(uid, "+FLAGS", "\\Seen")
    except Exception as e:
        logger.warning("IMAP mark seen error: %s", e)


def _extract_prices_from_text(text: str) -> list[tuple[str, Decimal]]:
    """Extract (product_name, price) pairs from plain text."""
    results = []
    for line in text.split("\n"):
        line = line.strip()
        if not FISH_RE.search(line):
            continue
        nums = PRICE_NUM_RE.findall(line)
        for n in nums:
            try:
                v = Decimal(n.replace(",", "."))
                if 20 < v < 200_000:
                    # Name = part before first number
                    name = re.split(r"\d", line)[0].strip()
                    if len(name) > 2:
                        results.append((name[:200], v))
                    break
            except InvalidOperation:
                pass
    return results


def _extract_from_xlsx(data: bytes, source: str) -> list[PriceRecord]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        records = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(c).strip() if c is not None else "" for c in row]
                name = ""
                price = None
                for cell in cells:
                    if FISH_RE.search(cell) and len(cell) > 2 and not name:
                        name = cell[:200]
                    nums = PRICE_NUM_RE.findall(cell)
                    for n in nums:
                        try:
                            v = Decimal(n.replace(",", "."))
                            if 20 < v < 200_000 and price is None:
                                price = v
                        except InvalidOperation:
                            pass
                if name and price:
                    records.append(PriceRecord(
                        raw_name=name,
                        price_rub=price,
                        source="email_xlsx",
                        source_url=source,
                    ))
        return records
    except Exception as e:
        logger.warning("xlsx parse error: %s", e)
        return []


def _extract_from_pdf(data: bytes, source: str) -> list[PriceRecord]:
    try:
        import pdfplumber
        records = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages[:15]:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        cells = [str(c).strip() if c else "" for c in row]
                        name = ""
                        price = None
                        for cell in cells:
                            if FISH_RE.search(cell) and len(cell) > 2 and not name:
                                name = cell[:200]
                            nums = PRICE_NUM_RE.findall(cell)
                            for n in nums:
                                try:
                                    v = Decimal(n.replace(",", "."))
                                    if 20 < v < 200_000 and price is None:
                                        price = v
                                except InvalidOperation:
                                    pass
                        if name and price:
                            records.append(PriceRecord(
                                raw_name=name,
                                price_rub=price,
                                source="email_pdf",
                                source_url=source,
                            ))
                if not tables:
                    text = page.extract_text() or ""
                    for name, price in _extract_prices_from_text(text):
                        records.append(PriceRecord(
                            raw_name=name,
                            price_rub=price,
                            source="email_pdf",
                            source_url=source,
                        ))
        return records
    except Exception as e:
        logger.warning("pdf parse error: %s", e)
        return []


async def _llm_extract_from_text(text: str, sender: str) -> list[PriceRecord]:
    """Use Claude to extract prices from email body or unknown format."""
    if len(text) > 6000:
        text = text[:6000]
    try:
        import json
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": (
                    "Извлеки из текста письма цены на рыбу и морепродукты. "
                    "Верни ТОЛЬКО JSON: "
                    '[{"name": "треска б/г", "price": 182}, ...] '
                    "Если ничего нет — []"
                )},
                {"role": "user", "content": f"От: {sender}\n\n{text}"},
            ],
        )
        raw = response.choices[0].message.content.strip()
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return []
        data = json.loads(m.group(0))
        records = []
        for item in data:
            try:
                price = Decimal(str(item["price"]))
                name = str(item["name"]).strip()
                if name and 20 < price < 200_000:
                    records.append(PriceRecord(
                        raw_name=name[:200],
                        price_rub=price,
                        source="email_llm",
                        source_url=f"email:{sender}",
                        supplier_name=sender or None,
                    ))
            except (KeyError, InvalidOperation):
                pass
        return records
    except Exception as e:
        logger.warning("LLM email extract error: %s", e)
        return []


@dataclass
class EmailParseResult:
    msg: EmailMessage
    records: list[PriceRecord]
    is_price_request: bool   # клиент просит прайс → нужен автоответ
    is_supplier: bool        # письмо от известного поставщика


async def process_inbox(supplier_emails: set[str] | None = None) -> list[EmailParseResult]:
    """
    Fetch unseen emails, extract prices, return results.
    supplier_emails: set of known supplier email addresses for matching.
    """
    msgs = await asyncio.to_thread(_fetch_emails_sync, 30)
    if not msgs:
        return []

    supplier_emails = supplier_emails or set()
    results = []
    seen_uids = []

    for msg in msgs:
        is_price_request = REQUEST_SUBJECT_RE.search(msg.subject) is not None
        is_supplier = (
            msg.sender_email in supplier_emails
            or PRICE_SUBJECT_RE.search(msg.subject) is not None
        )

        records: list[PriceRecord] = []

        # Try to extract from attachments
        for att in msg.attachments:
            fn = att["filename"].lower()
            source = f"email:{msg.sender_email}:{att['filename']}"
            if fn.endswith((".xlsx", ".xls")):
                records.extend(_extract_from_xlsx(att["data"], source))
            elif fn.endswith(".pdf"):
                records.extend(_extract_from_pdf(att["data"], source))

        # If no structured attachments, try body text
        if not records and (is_supplier or FISH_RE.search(msg.body)):
            # Try plain text first
            text_records = []
            for name, price in _extract_prices_from_text(msg.body):
                text_records.append(PriceRecord(
                    raw_name=name, price_rub=price,
                    source="email_text",
                    source_url=f"email:{msg.sender_email}",
                    supplier_name=msg.sender or None,
                ))
            if text_records:
                records.extend(text_records)
            else:
                # LLM fallback
                llm_records = await _llm_extract_from_text(msg.body, msg.sender_email)
                records.extend(llm_records)

        # Tag supplier name on all records
        for rec in records:
            if not rec.supplier_name:
                rec.supplier_name = msg.sender or msg.sender_email

        if records or is_price_request:
            results.append(EmailParseResult(
                msg=msg,
                records=records,
                is_price_request=is_price_request,
                is_supplier=is_supplier,
            ))
            seen_uids.append(msg.uid)

    # Mark processed messages as read
    if seen_uids:
        await asyncio.to_thread(_mark_seen_sync, seen_uids)

    logger.info(
        "IMAP: processed %d messages, %d with prices, %d price requests",
        len(msgs),
        sum(1 for r in results if r.records),
        sum(1 for r in results if r.is_price_request),
    )
    return results
