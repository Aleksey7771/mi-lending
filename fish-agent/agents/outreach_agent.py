"""
OutreachAgent: email-рассылка прайса и КП.

Схема:
  1. Собрать получателей из таблицы clients (у кого есть email)
  2. Сгенерировать PDF прайс
  3. Отправить каждому персональное письмо с вложением
  4. Вернуть статистику

SMTP: Mail.ru (ssl port 465) или любой другой.
"""
import asyncio
import logging
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


def _is_smtp_configured() -> bool:
    return bool(settings.smtp_user and settings.smtp_password)


def _send_email_sync(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    pdf_path: str | None = None,
    pdf_filename: str = "прайс.pdf",
) -> None:
    """Synchronous SMTP send — called via asyncio.to_thread."""
    msg = MIMEMultipart("mixed")
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
    msg["Subject"] = subject

    # HTML body
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    # PDF attachment
    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()
        attachment = MIMEApplication(pdf_data, _subtype="pdf")
        attachment.add_header(
            "Content-Disposition", "attachment",
            filename=("utf-8", "", pdf_filename),
        )
        msg.attach(attachment)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=30) as server:
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, to_email, msg.as_bytes())


def _build_email_body(
    client_name: str,
    company_name: str,
    phone: str,
    telegram: str,
) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">

<p>Добрый день{", " + client_name if client_name else ""}!</p>

<p>Высылаем актуальный прайс на рыбу и морепродукты с Дальнего Востока.</p>

<p>В нашем ассортименте:</p>
<ul>
  <li>Белая рыба: треска, минтай, навага, камбала, палтус</li>
  <li>Красная рыба: горбуша, кета, нерка, кижуч, лосось, семга</li>
  <li>Морепродукты: краб, гребешок, морской ёж</li>
</ul>

<p>Прайс-лист во вложении. Готовы обсудить объёмы и условия.</p>

<p style="margin-top: 20px;">
  <strong>{company_name}</strong><br>
  📞 {phone}<br>
  💬 {telegram}
</p>

</body></html>"""


async def send_preis_to_all(
    pdf_path: str,
    limit: int = 0,
    city_filter: str = "",
    type_filter: str = "",
) -> dict:
    """
    Отправить прайс всем клиентам с email.
    Возвращает: {"sent": N, "failed": N, "skipped": N, "recipients": [...]}
    """
    if not _is_smtp_configured():
        return {"error": "SMTP не настроен. Укажи SMTP_USER и SMTP_PASSWORD в .env"}

    from sqlalchemy import select
    from memory.db import AsyncSessionFactory
    from memory.models import Client

    async with AsyncSessionFactory() as session:
        q = select(Client).where(
            Client.is_active == True,
            Client.email.isnot(None),
            Client.email != "",
        )
        if city_filter:
            q = q.where(Client.city.ilike(f"%{city_filter}%"))
        if type_filter:
            q = q.where(Client.type.ilike(f"%{type_filter}%"))
        q = q.order_by(Client.city, Client.name)
        if limit:
            q = q.limit(limit)
        clients = (await session.execute(q)).scalars().all()

    if not clients:
        return {"error": "Нет клиентов с email" + (f" в «{city_filter}»" if city_filter else "")}

    from datetime import datetime
    today = datetime.now().strftime("%d.%m.%Y")
    subject = f"Прайс на рыбу и морепродукты — {today}"
    pdf_filename = f"прайс_{datetime.now().strftime('%Y%m%d')}.pdf"

    sent = 0
    failed = 0
    failed_emails = []

    for client in clients:
        body = _build_email_body(
            client_name=client.name or "",
            company_name=settings.company_name,
            phone=settings.company_phone,
            telegram=settings.company_telegram or "@aleksey_fish",
        )
        try:
            await asyncio.to_thread(
                _send_email_sync,
                client.email,
                client.name or "",
                subject,
                body,
                pdf_path,
                pdf_filename,
            )
            sent += 1
            logger.info("email sent → %s <%s>", client.name, client.email)
            await asyncio.sleep(0.3)  # не спамить сервер
        except Exception as e:
            failed += 1
            failed_emails.append(client.email)
            logger.warning("email failed %s: %s", client.email, e)

    return {
        "sent": sent,
        "failed": failed,
        "total": len(clients),
        "failed_emails": failed_emails,
    }


async def get_email_preview(
    city_filter: str = "",
    type_filter: str = "",
) -> dict:
    """Показать сколько получателей и пример письма перед отправкой."""
    from sqlalchemy import select, func
    from memory.db import AsyncSessionFactory
    from memory.models import Client

    async with AsyncSessionFactory() as session:
        q = select(func.count()).select_from(Client).where(
            Client.is_active == True,
            Client.email.isnot(None),
            Client.email != "",
        )
        if city_filter:
            q = q.where(Client.city.ilike(f"%{city_filter}%"))
        if type_filter:
            q = q.where(Client.type.ilike(f"%{type_filter}%"))
        total = (await session.execute(q)).scalar() or 0

        # Sample recipients for preview
        q2 = select(Client).where(
            Client.is_active == True,
            Client.email.isnot(None),
            Client.email != "",
        )
        if city_filter:
            q2 = q2.where(Client.city.ilike(f"%{city_filter}%"))
        if type_filter:
            q2 = q2.where(Client.type.ilike(f"%{type_filter}%"))
        sample = (await session.execute(q2.limit(5))).scalars().all()

    return {
        "total": total,
        "sample": [{"name": c.name, "email": c.email, "city": c.city} for c in sample],
        "configured": _is_smtp_configured(),
    }
