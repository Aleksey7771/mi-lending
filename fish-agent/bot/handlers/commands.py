import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from memory.db import AsyncSessionFactory

logger = logging.getLogger(__name__)
router = Router()


def _main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Прайс (PDF)", callback_data="cmd_preis"),
        InlineKeyboardButton(text="💰 Мои цены", callback_data="cmd_prices"),
    )
    builder.row(
        InlineKeyboardButton(text="📄 Коммерческое предложение", callback_data="cmd_kp_prompt"),
    )
    builder.row(
        InlineKeyboardButton(text="🏭 Клиенты (опт)", callback_data="cmd_suppliers"),
        InlineKeyboardButton(text="🏪 Клиенты (розн.)", callback_data="cmd_clients"),
    )
    builder.row(
        InlineKeyboardButton(text="📞 Список обзвона", callback_data="cmd_call_list"),
        InlineKeyboardButton(text="📧 Рассылка", callback_data="cmd_broadcast"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Канал", callback_data="cmd_channel"),
        InlineKeyboardButton(text="❓ Справка", callback_data="cmd_help"),
    )
    return builder.as_markup()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я твой торговый агент по рыбе.\n\n"
        "Умею:\n"
        "• Следить за ценами поставщиков\n"
        "• Генерировать PDF прайс и коммерческие предложения\n"
        "• Обновлять цены по голосовой команде\n\n"
        "Или пиши свободно — например:\n"
        "<i>«обнови треску 182 Иванов»</i>",
        reply_markup=_main_keyboard(),
    )


@router.message(Command("помощь"))
@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📌 <b>Примеры команд:</b>\n\n"
        "✏️ Обновить цену:\n"
        "<code>обнови горбуша 95 Петров</code>\n\n"
        "📊 Прайс:\n"
        "<code>/preis</code> — PDF за 10 секунд\n\n"
        "📄 Коммерческое предложение:\n"
        "<code>/kp Марина</code> — КП для клиента\n\n"
        "💬 Вопрос о ценах:\n"
        "<code>почём треска у всех поставщиков?</code>\n\n"
        "📞 Обзвон клиентов:\n"
        "<code>/обзвон Владивосток рестораны</code>\n"
        "<code>/lead Ресторан Море интерес</code>\n\n"
        "✍️ Пост для соцсетей:\n"
        "<code>напиши пост про горбушу 95 рублей</code>",
        reply_markup=_main_keyboard(),
    )


@router.message(Command("preis"))
async def cmd_preis(message: Message) -> None:
    await message.answer("⏳ Генерирую PDF прайс...")
    try:
        from agents.pdf_agent import build_preis_pdf
        async with AsyncSessionFactory() as session:
            path = await build_preis_pdf(session)
        await message.answer_document(
            FSInputFile(path, filename="прайс.pdf"),
            caption="Актуальный прайс готов.",
        )
    except Exception as e:
        logger.exception("preis generation failed")
        await message.answer(f"Не удалось сгенерировать прайс: {e}")


@router.message(Command("kp"))
async def cmd_kp(message: Message) -> None:
    # Extract client name from command args
    args = (message.text or "").split(maxsplit=1)
    client_query = args[1].strip() if len(args) > 1 else ""

    if not client_query:
        await message.answer("Укажи клиента: /kp Марина\nили /kp Ресторан Море")
        return

    await message.answer(f"⏳ Генерирую КП для «{client_query}»...")
    try:
        from agents.pdf_agent import build_kp_pdf
        async with AsyncSessionFactory() as session:
            path = await build_kp_pdf(session, client_query)
        if path is None:
            await message.answer(
                f"Клиент «{client_query}» не найден в базе.\n"
                "Добавь: «Добавь клиента: Марина, ресторан, Новосибирск»"
            )
            return
        await message.answer_document(
            FSInputFile(path, filename=f"КП_{client_query}.pdf"),
            caption=f"КП для {client_query} готово.",
        )
    except Exception as e:
        logger.exception("kp generation failed")
        await message.answer(f"Не удалось сгенерировать КП: {e}")


@router.message(Command("update"))
async def cmd_update(message: Message) -> None:
    # Delegate to free text handler (same logic)
    # The text already starts with /update, strip it
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Формат: /update треска б/г 182 Иванов")
        return
    # Reuse free-text flow
    message.text = args[1]
    from bot.handlers.text import handle_free_text
    await handle_free_text(message)


@router.message(Command("прайс"))
@router.message(Command("цены"))
async def cmd_prices(message: Message) -> None:
    await message.answer("⏳ Загружаю текущие цены...")
    from agents.price_agent import format_morning_digest
    async with AsyncSessionFactory() as session:
        text = await format_morning_digest(session)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("почта"))
@router.message(Command("email"))
async def cmd_check_email(message: Message) -> None:
    """Проверить входящие вручную прямо сейчас."""
    if not __import__("config").settings.smtp_user:
        await message.answer(
            "⚠️ Email не настроен. Укажи SMTP_USER и SMTP_PASSWORD в .env"
        )
        return
    await message.answer("📬 Проверяю входящие...")
    from scheduler.tasks.email_check import run_email_check
    result = await run_email_check()
    if result["processed"] == 0:
        await message.answer("📭 Новых писем нет.")
    else:
        lines = [f"✅ Обработано писем: {result['processed']}"]
        if result["prices_saved"]:
            lines.append(f"💰 Цен сохранено: {result['prices_saved']}")
        if result["auto_replies"]:
            lines.append(f"↩️ Автоответов отправлено: {result['auto_replies']}")
        await message.answer("\n".join(lines))


@router.message(Command("broadcast"))
@router.message(Command("рассылка"))
async def cmd_broadcast(message: Message) -> None:
    """Рассылка прайса по email всем клиентам."""
    args = (message.text or "").split(maxsplit=3)
    city_filter = ""
    type_filter = ""
    # Парсим необязательные аргументы: /рассылка [город] [тип]
    if len(args) >= 2 and args[1].lower() not in ("все", "all", "отправить"):
        city_filter = args[1].strip()
    if len(args) >= 3:
        type_filter = args[2].strip()

    from agents.outreach_agent import get_email_preview
    preview = await get_email_preview(city_filter=city_filter, type_filter=type_filter)

    if not preview["configured"]:
        await message.answer(
            "⚠️ Email не настроен.\n\n"
            "В файле <code>.env</code> укажи:\n"
            "<code>SMTP_USER=твой@mail.ru</code>\n"
            "<code>SMTP_PASSWORD=пароль_приложения</code>\n\n"
            "Для Mail.ru: Настройки → Безопасность → Пароли приложений"
        )
        return

    if preview["total"] == 0:
        hint = f" в «{city_filter}»" if city_filter else ""
        await message.answer(
            f"Нет клиентов с email и активным согласием на рассылку{hint}."
        )
        return

    filter_info = ""
    if city_filter:
        filter_info += f"\nГород: {city_filter}"
    if type_filter:
        filter_info += f"\nТип: {type_filter}"

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    confirm_key = f"{city_filter}|{type_filter}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"📧 Отправить {preview['total']} письмам",
            callback_data=f"broadcast_send:{confirm_key}",
        ),
        InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel"),
    ]])

    await message.answer(
        f"📧 <b>Рассылка прайса</b>{filter_info}\n\n"
        f"Получателей с активным согласием: <b>{preview['total']}</b>\n\n"
        f"Тема: «Прайс на рыбу и морепродукты — сегодня»\n"
        f"Вложение: PDF прайс (будет сгенерирован автоматически)",
        reply_markup=keyboard,
    )


@router.message(Command("тренд"))
@router.message(Command("trend"))
async def cmd_trend(message: Message) -> None:
    """Показать историю цен по позиции."""
    args = (message.text or "").split(maxsplit=2)
    product_query = args[1].strip() if len(args) >= 2 else ""
    days = 30
    if len(args) >= 3:
        try:
            days = int(args[2])
        except ValueError:
            pass

    if not product_query:
        await message.answer(
            "Укажи позицию: <code>/тренд треска</code>\n"
            "Или за другой период: <code>/тренд горбуша 14</code>"
        )
        return

    await message.answer(f"📊 Собираю данные по «{product_query}»...")
    from agents.trend_agent import get_price_history, format_trend_message
    async with AsyncSessionFactory() as session:
        data = await get_price_history(session, product_query, days=days)

    if data is None:
        await message.answer(f"Позиция «{product_query}» не найдена в базе.")
        return

    await message.answer(format_trend_message(data), parse_mode="HTML")


@router.message(Command("кто"))
async def cmd_who(message: Message) -> None:
    """Поиск компании по названию — показывает все данные."""
    args = (message.text or "").split(maxsplit=1)
    query = args[1].strip() if len(args) > 1 else ""
    if not query:
        await message.answer("Укажи название: <code>/кто Сахалин Фиш</code>", parse_mode="HTML")
        return

    from sqlalchemy import select, or_
    from memory.models import Supplier, Client
    q = f"%{query}%"

    async with AsyncSessionFactory() as session:
        suppliers = (await session.execute(
            select(Supplier).where(Supplier.name.ilike(q)).limit(5)
        )).scalars().all()
        clients = (await session.execute(
            select(Client).where(Client.name.ilike(q)).limit(5)
        )).scalars().all()

    if not suppliers and not clients:
        await message.answer(f"Компания «{query}» не найдена.")
        return

    lines = []
    for s in suppliers:
        lines.append(f"🏭 <b>{s.name}</b>")
        if s.region:   lines.append(f"📍 {s.region}")
        if s.phone:    lines.append(f"📞 {s.phone}")
        if s.telegram: lines.append(f"💬 {s.telegram}")
        if s.email:    lines.append(f"📧 {s.email}")
        if s.notes:    lines.append(f"📝 {s.notes}")
        lines.append("")

    for c in clients:
        lines.append(f"🏪 <b>{c.name}</b>")
        if c.type:     lines.append(f"🏷 {c.type}")
        if c.city:     lines.append(f"📍 {c.city}")
        if c.address:  lines.append(f"🗺 {c.address}")
        if c.phone:    lines.append(f"📞 {c.phone}")
        if c.telegram: lines.append(f"💬 {c.telegram}")
        if c.email:    lines.append(f"📧 {c.email}")
        if c.notes:    lines.append(f"📝 {c.notes}")
        lines.append("")

    await message.answer("\n".join(lines).strip(), parse_mode="HTML")


@router.message(Command("call_list"))
@router.message(Command("обзвон"))
async def cmd_call_list(message: Message) -> None:
    """Список для обзвона из 2ГИС базы."""
    args = (message.text or "").split(maxsplit=2)
    city_filter = ""
    type_filter = ""
    if len(args) >= 2:
        city_filter = args[1].strip()
    if len(args) >= 3:
        type_filter = args[2].strip()

    from sqlalchemy import select, func
    from memory.models import Client

    async with AsyncSessionFactory() as session:
        q = select(Client).where(
            Client.is_active == True,
            Client.phone.isnot(None),
        )
        if city_filter and city_filter.lower() not in ("все", "all"):
            q = q.where(Client.city.ilike(f"%{city_filter}%"))
        if type_filter:
            q = q.where(Client.type.ilike(f"%{type_filter}%"))
        q = q.order_by(Client.city, Client.name)

        rows = (await session.execute(q)).scalars().all()

    if not rows:
        hint = f" в городе «{city_filter}»" if city_filter else ""
        await message.answer(f"Контактов{hint} с телефоном не найдено.")
        return

    # Группировка по городу
    by_city: dict[str, list] = {}
    for c in rows:
        by_city.setdefault(c.city or "—", []).append(c)

    lines = [f"📞 <b>Список для обзвона — {len(rows)} контактов</b>"]
    if city_filter:
        lines[0] += f" ({city_filter})"
    lines.append("")

    n = 1
    for city, clients in sorted(by_city.items()):
        lines.append(f"<b>{city}</b>")
        for c in clients:
            ctype = f" ({c.type})" if c.type else ""
            lines.append(f"  {n}. {c.name}{ctype}")
            lines.append(f"     📞 {c.phone}")
            n += 1
        lines.append("")

    lines.append("<i>Обновить статус: /lead [название] [статус]</i>")
    lines.append("<i>Статусы: новый · позвонил · интерес · клиент · отказ</i>")

    full = "\n".join(lines)
    for i in range(0, len(full), 3800):
        await message.answer(full[i:i + 3800], parse_mode="HTML")


@router.message(Command("lead"))
async def cmd_lead_status(message: Message) -> None:
    """Обновить статус лида после звонка."""
    args = (message.text or "").split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "Формат: <code>/lead Название статус</code>\n\n"
            "Статусы: <code>новый</code> · <code>позвонил</code> · "
            "<code>интерес</code> · <code>клиент</code> · <code>отказ</code>"
        )
        return

    name_query = args[1].strip()
    status_raw = args[2].strip().lower()

    STATUS_MAP = {
        "новый": "new", "new": "new",
        "позвонил": "contacted", "contacted": "contacted",
        "интерес": "interested", "interested": "interested",
        "клиент": "converted", "converted": "converted",
        "отказ": "rejected", "rejected": "rejected",
    }
    status = STATUS_MAP.get(status_raw)
    if not status:
        await message.answer(
            f"Неизвестный статус «{status_raw}».\n"
            "Доступные: новый, позвонил, интерес, клиент, отказ"
        )
        return

    from sqlalchemy import select, update
    from memory.models import Client
    from datetime import datetime

    async with AsyncSessionFactory() as session:
        rows = (await session.execute(
            select(Client).where(Client.name.ilike(f"%{name_query}%"), Client.is_active == True)
        )).scalars().all()

        if not rows:
            await message.answer(f"Клиент «{name_query}» не найден.")
            return

        if len(rows) > 1:
            names = "\n".join(f"• {c.name} ({c.city or '—'})" for c in rows[:5])
            await message.answer(
                f"Найдено несколько ({len(rows)}), уточни:\n{names}"
            )
            return

        client = rows[0]
        # Сохраняем статус в notes (пока нет отдельного поля)
        note_prefix = f"[{status_raw.upper()} {datetime.now().strftime('%d.%m')}]"
        old_notes = client.notes or ""
        # Убираем предыдущий статус если был
        import re
        old_notes = re.sub(r"\[(?:НОВЫЙ|ПОЗВОНИЛ|ИНТЕРЕС|КЛИЕНТ|ОТКАЗ|NEW|CONTACTED|INTERESTED|CONVERTED|REJECTED)[^\]]*\]\s*", "", old_notes).strip()
        client.notes = f"{note_prefix} {old_notes}".strip()
        await session.commit()

    STATUS_RU = {
        "new": "Новый", "contacted": "Позвонил", "interested": "Есть интерес",
        "converted": "Стал клиентом", "rejected": "Отказ",
    }
    await message.answer(
        f"✅ Статус обновлён: <b>{client.name}</b> → {STATUS_RU[status]}"
    )


@router.message(Command("поставщики"))
async def cmd_suppliers(message: Message) -> None:
    from sqlalchemy import select
    from memory.models import Supplier
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(
            select(Supplier)
            .where(Supplier.is_active == True)
            .where(Supplier.region.like("Россия%"))
            .order_by(Supplier.region, Supplier.name)
        )).scalars().all()
    if not rows:
        await message.answer("Российские поставщики не найдены.")
        return
    by_region: dict[str, list] = {}
    for s in rows:
        parts = (s.region or "").split(",")
        short = parts[1].strip() if len(parts) > 1 else "Россия"
        by_region.setdefault(short, []).append(s)
    lines = [f"🇷🇺 <b>Поставщики (Россия) — {len(rows)} компаний</b>"]
    for region, suppliers in sorted(by_region.items()):
        lines.append(f"\n<b>{region}</b>")
        for s in suppliers[:10]:
            contact = s.telegram or s.phone or s.email or "—"
            lines.append(f"  • {s.name} — {contact}")
        if len(suppliers) > 10:
            lines.append(f"  <i>...ещё {len(suppliers) - 10}</i>")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("channel"))
@router.message(Command("канал"))
async def cmd_channel(message: Message) -> None:
    """Explain the approval-first Postmately publishing flow."""
    await message.answer(
        "Публикации в Telegram идут через Postmately.\n"
        "Напишите «напиши пост про ...» — я пришлю черновик. "
        "Пост выйдет только после нажатия «Одобрить и опубликовать».",
        parse_mode=None,
    )


@router.message(Command("publish_"))
async def cmd_publish_shortcut(message: Message) -> None:
    await message.answer(
        "Эта команда устарела. Создайте новый пост — бот пришлёт его на одобрение.",
        parse_mode=None,
    )
