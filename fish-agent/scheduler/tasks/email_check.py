"""
Scheduled task: check inbox every 15 minutes.
  - Extract prices from supplier attachments → save to DB → notify owner
  - Auto-reply to price requests with PDF preis
"""
import logging
from decimal import Decimal

from aiogram import Bot
from sqlalchemy import select

from memory.db import AsyncSessionFactory
from memory.models import Product, Supplier, SupplierPrice
from parsers.email_parser import process_inbox
from parsers.fuzzy_match import normalize_product_name

logger = logging.getLogger(__name__)


async def _get_supplier_emails() -> set[str]:
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(
            select(Supplier.email).where(
                Supplier.is_active == True,
                Supplier.email.isnot(None),
            )
        )).scalars().all()
    return {e.lower().strip() for e in rows if e}


async def _save_price_records(records) -> int:
    if not records:
        return 0
    async with AsyncSessionFactory() as session:
        products_rows = await session.execute(
            select(Product.id, Product.name, Product.aliases).where(Product.is_active == True)
        )
        products = [(r.id, r.name, r.aliases or []) for r in products_rows]

        suppliers_rows = await session.execute(
            select(Supplier.id, Supplier.name).where(Supplier.is_active == True)
        )
        supplier_map = {s.name.lower(): s.id for s in suppliers_rows}

        saved = 0
        for rec in records:
            match = normalize_product_name(rec.raw_name, products)
            product_id = match.product_id if match else None

            supplier_id = None
            if rec.supplier_name:
                for sname, sid in supplier_map.items():
                    if rec.supplier_name.lower() in sname or sname in rec.supplier_name.lower():
                        supplier_id = sid
                        break

            sp = SupplierPrice(
                product_id=product_id,
                supplier_id=supplier_id,
                price_rub=rec.price_rub,
                source=rec.source,
                source_url=rec.source_url or "",
                raw_name=rec.raw_name if product_id is None else None,
            )
            session.add(sp)
            saved += 1

        await session.commit()
    return saved


async def _auto_reply(sender_email: str, sender_name: str, pdf_path: str) -> None:
    """Send PDF preis as auto-reply to price request."""
    try:
        from agents.outreach_agent import _send_email_sync
        from config import settings
        import asyncio
        from datetime import datetime

        subject = f"Re: Прайс на рыбу и морепродукты — {datetime.now().strftime('%d.%m.%Y')}"
        body = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<p>Добрый день{", " + sender_name if sender_name else ""}!</p>
<p>Высылаем актуальный прайс во вложении.</p>
<p>По вопросам: {settings.company_phone} / {settings.company_telegram or '@aleksey_fish'}</p>
<p><strong>{settings.company_name}</strong></p>
</body></html>"""

        await asyncio.to_thread(
            _send_email_sync,
            sender_email, sender_name, subject, body,
            pdf_path, f"прайс_{datetime.now().strftime('%Y%m%d')}.pdf",
        )
        logger.info("auto-reply sent → %s", sender_email)
    except Exception as e:
        logger.warning("auto-reply failed %s: %s", sender_email, e)


async def run_email_check(bot: Bot | None = None, owner_id: int | None = None) -> dict:
    """
    Main scheduled job: check inbox, process, notify.
    Returns summary dict.
    """
    supplier_emails = await _get_supplier_emails()
    results = await process_inbox(supplier_emails=supplier_emails)

    if not results:
        return {"processed": 0, "prices_saved": 0, "auto_replies": 0}

    total_saved = 0
    auto_replies = 0
    notify_lines = []
    pdf_path = None

    for result in results:
        msg = result.msg

        # Save prices to DB
        if result.records:
            saved = await _save_price_records(result.records)
            total_saved += saved

            # Build notification line
            products_found = list({r.raw_name for r in result.records})[:4]
            products_str = ", ".join(products_found)
            if len(products_found) < len(result.records):
                products_str += f" и ещё {len(result.records) - len(products_found)}"
            notify_lines.append(
                f"📧 <b>{msg.sender or msg.sender_email}</b>\n"
                f"   «{msg.subject[:60]}»\n"
                f"   💰 {saved} цен: {products_str}"
            )

        # Auto-reply to price requests
        if result.is_price_request and bot and owner_id:
            # Generate PDF once
            if pdf_path is None:
                try:
                    from agents.pdf_agent import build_preis_pdf
                    async with AsyncSessionFactory() as session:
                        pdf_path = await build_preis_pdf(session)
                except Exception as e:
                    logger.warning("pdf for auto-reply failed: %s", e)

            if pdf_path:
                await _auto_reply(msg.sender_email, msg.sender, pdf_path)
                auto_replies += 1
                notify_lines.append(
                    f"↩️ Автоответ → {msg.sender_email} (запрос прайса)"
                )

    # Send Telegram notification to owner
    if notify_lines and bot and owner_id:
        header = f"📬 <b>Новые письма ({len(results)})</b>\n"
        text = header + "\n\n".join(notify_lines)
        try:
            await bot.send_message(owner_id, text, parse_mode="HTML")
        except Exception as e:
            logger.warning("notify owner failed: %s", e)

    summary = {
        "processed": len(results),
        "prices_saved": total_saved,
        "auto_replies": auto_replies,
    }
    logger.info("Email check done: %s", summary)
    return summary
