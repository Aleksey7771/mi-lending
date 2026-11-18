from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile

from memory.db import AsyncSessionFactory

router = Router()


@router.callback_query(F.data == "cmd_preis")
async def cb_preis(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("⏳ Генерирую PDF прайс...")
    try:
        from agents.pdf_agent import build_preis_pdf
        async with AsyncSessionFactory() as session:
            path = await build_preis_pdf(session)
        await callback.message.answer_document(
            FSInputFile(path, filename="прайс.pdf"),
            caption="Актуальный прайс готов.",
        )
    except Exception as e:
        await callback.message.answer(f"Не удалось сгенерировать прайс: {e}")


@router.callback_query(F.data == "cmd_prices")
async def cb_prices(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("⏳ Загружаю текущие цены...")
    from agents.price_agent import format_morning_digest
    async with AsyncSessionFactory() as session:
        text = await format_morning_digest(session)
    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "cmd_kp_prompt")
async def cb_kp_prompt(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "📄 Укажи имя или название клиента:\n\n"
        "Например: <code>/kp Марина</code> или <code>/kp Ресторан Море</code>"
    )


@router.callback_query(F.data == "cmd_suppliers")
async def cb_suppliers(callback: CallbackQuery) -> None:
    await callback.answer()
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
        await callback.message.answer("Клиенты (опт) не найдены в базе.")
        return

    by_region: dict[str, list] = {}
    for s in rows:
        parts = (s.region or "").split(",")
        short = parts[1].strip() if len(parts) > 1 else "Россия"
        by_region.setdefault(short, []).append(s)

    lines = [f"🏭 <b>Клиенты (опт) — {len(rows)} компаний</b>\n"
             f"<i>Нажми /кто [название] для подробностей</i>"]
    for region, suppliers in sorted(by_region.items()):
        lines.append(f"\n<b>{region}</b>")
        for s in suppliers[:10]:
            contacts = " | ".join(filter(None, [s.phone, s.telegram, s.email]))
            contact_str = contacts or "—"
            lines.append(f"  • {s.name} — {contact_str}")
        if len(suppliers) > 10:
            lines.append(f"  <i>...ещё {len(suppliers) - 10}</i>")

    full = "\n".join(lines)
    for i in range(0, len(full), 3800):
        await callback.message.answer(full[i:i + 3800], parse_mode="HTML")


@router.callback_query(F.data.startswith("sup_detail:"))
async def cb_supplier_detail(callback: CallbackQuery) -> None:
    await callback.answer()
    supplier_id = int(callback.data.split(":")[1])
    from sqlalchemy import select
    from memory.models import Supplier
    async with AsyncSessionFactory() as session:
        s = (await session.execute(
            select(Supplier).where(Supplier.id == supplier_id)
        )).scalar_one_or_none()
    if not s:
        await callback.message.answer("Компания не найдена.")
        return
    lines = [f"🏭 <b>{s.name}</b>"]
    if s.region:
        lines.append(f"📍 {s.region}")
    if s.phone:
        lines.append(f"📞 {s.phone}")
    if s.telegram:
        lines.append(f"💬 {s.telegram}")
    if s.email:
        lines.append(f"📧 {s.email}")
    if s.notes:
        lines.append(f"\n📝 {s.notes}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "cmd_clients")
async def cb_clients(callback: CallbackQuery) -> None:
    await callback.answer()
    from sqlalchemy import select
    from memory.models import Client
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(
            select(Client).where(Client.is_active == True).order_by(Client.city, Client.name)
        )).scalars().all()
    if not rows:
        await callback.message.answer(
            "👥 Клиентов пока нет.\n\n"
            "Добавить: напиши боту\n"
            "<code>добавь клиента: Марина, ресторан, Москва, +7 999 000-00-00</code>"
        )
        return

    # Группируем по городу
    by_city: dict[str, list] = {}
    for c in rows:
        city = c.city or "Без города"
        by_city.setdefault(city, []).append(c)

    lines = [f"👥 <b>Клиенты — {len(rows)} компаний</b>"]
    for city, clients in sorted(by_city.items()):
        lines.append(f"\n<b>{city}</b>")
        for c in clients[:8]:
            contact = c.telegram or c.phone or "—"
            ctype = f" ({c.type})" if c.type else ""
            lines.append(f"  • {c.name}{ctype} — {contact}")
        if len(clients) > 8:
            lines.append(f"  <i>...ещё {len(clients) - 8}</i>")

    # Telegram: макс ~4000 символов на сообщение — режем на части
    full = "\n".join(lines)
    chunk_size = 3800
    for i in range(0, len(full), chunk_size):
        await callback.message.answer(full[i:i + chunk_size], parse_mode="HTML")

    await callback.message.answer(
        "➕ <i>Добавить: «добавь клиента: Имя, тип, город, телефон»</i>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("broadcast_send:"))
async def cb_broadcast_send(callback: CallbackQuery) -> None:
    await callback.answer("Запускаю рассылку...")
    key = callback.data.split(":", 1)[1]
    parts = key.split("|", 1)
    city_filter = parts[0] if parts[0] else ""
    type_filter = parts[1] if len(parts) > 1 and parts[1] else ""

    await callback.message.answer("⏳ Генерирую PDF прайс и начинаю рассылку...")
    try:
        from agents.pdf_agent import build_preis_pdf
        from agents.outreach_agent import send_preis_to_all
        async with AsyncSessionFactory() as session:
            pdf_path = await build_preis_pdf(session)

        result = await send_preis_to_all(
            pdf_path=pdf_path,
            city_filter=city_filter,
            type_filter=type_filter,
        )

        if "error" in result:
            await callback.message.answer(f"⚠️ {result['error']}")
            return

        lines = [
            f"✅ <b>Рассылка завершена</b>",
            f"Отправлено: {result['sent']} из {result['total']}",
        ]
        if result["failed"]:
            lines.append(f"Ошибок: {result['failed']}")
            lines.append("Не доставлено: " + ", ".join(result["failed_emails"][:5]))
        await callback.message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка рассылки: {e}")


@router.callback_query(F.data == "broadcast_cancel")
async def cb_broadcast_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Отменено")
    await callback.message.answer("Рассылка отменена.")


@router.callback_query(F.data == "cmd_broadcast")
async def cb_broadcast(callback: CallbackQuery) -> None:
    await callback.answer()
    from bot.handlers.commands import cmd_broadcast
    await cmd_broadcast(callback.message)


@router.callback_query(F.data == "cmd_call_list")
async def cb_call_list(callback: CallbackQuery) -> None:
    await callback.answer()
    from bot.handlers.commands import cmd_call_list
    await cmd_call_list(callback.message)


@router.callback_query(F.data == "cmd_help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.answer()
    from bot.handlers.commands import cmd_help
    await cmd_help(callback.message)


@router.callback_query(F.data == "refresh_preis")
async def cb_refresh_preis(callback: CallbackQuery) -> None:
    await callback.answer("Обновляю прайс...")
    await callback.message.answer("⏳ Запускаю парсеры цен...")
    try:
        from scheduler.tasks.price_update import run_parsers
        count = await run_parsers()
        await callback.message.answer(f"✅ Прайс обновлён: {count} записей")
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка обновления: {e}")


@router.callback_query(F.data == "download_pdf")
async def cb_download_pdf(callback: CallbackQuery) -> None:
    await callback.answer("Генерирую PDF...")
    await callback.message.answer("⏳ Генерирую PDF прайс...")
    try:
        from agents.pdf_agent import build_preis_pdf
        from aiogram.types import FSInputFile
        async with AsyncSessionFactory() as session:
            path = await build_preis_pdf(session)
        await callback.message.answer_document(
            FSInputFile(path, filename="прайс.pdf"),
            caption="Актуальный прайс готов.",
        )
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка генерации PDF: {e}")


@router.callback_query(F.data.startswith("approve_price:"))
async def cb_approve_price(callback: CallbackQuery) -> None:
    # format: approve_price:{product_id}:{price}
    await callback.answer("Цена обновлена.")
    # TODO: подключить MemoryAgent


@router.callback_query(F.data.startswith("style:"))
async def cb_style_feedback(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 2)
    action = parts[1]
    example_id = int(parts[2]) if len(parts) > 2 else 0

    from agents.post_agent import update_style_score, generate_post, save_style_example
    from memory.db import AsyncSessionFactory
    from memory.models import StyleExample

    if action == "like":
        await update_style_score(example_id, 1)
        await callback.answer("👍 Запомнил — буду писать в таком стиле")
        # Remove feedback buttons
        await callback.message.edit_reply_markup(reply_markup=None)

    elif action == "dislike":
        await update_style_score(example_id, -1)
        await callback.answer("👎 Понял, переделываю...")
        # Get original post text to regenerate
        async with AsyncSessionFactory() as session:
            ex = await session.get(StyleExample, example_id)
            original_content = ex.content if ex else ""
        # Regenerate with same topic hint
        new_post = await generate_post(topic="тот же товар, другой стиль", price_info="")
        new_id = await save_style_example(new_post, score=0)
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="👍 Хорошо", callback_data=f"style:like:{new_id}"),
            InlineKeyboardButton(text="👎 Переделать", callback_data=f"style:dislike:{new_id}"),
            InlineKeyboardButton(text="✏️ Скопировать", callback_data=f"style:copy:{new_id}"),
        ]])
        await callback.message.answer(new_post, reply_markup=keyboard)
        await callback.message.edit_reply_markup(reply_markup=None)

    elif action == "copy":
        await callback.answer("Скопировано в буфер!")
        # Send post text as separate message so user can copy
        async with AsyncSessionFactory() as session:
            ex = await session.get(StyleExample, example_id)
        if ex:
            await callback.message.answer(
                f"<code>{ex.content}</code>",
                parse_mode="HTML",
            )
