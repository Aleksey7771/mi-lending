import logging
from decimal import Decimal

from aiogram import Router, F
from aiogram.types import Message

from agents.orchestrator import detect_intent
from agents.memory_agent import save_supplier_price, save_supplier, save_client
from memory.db import AsyncSessionFactory

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.voice | F.audio)
async def handle_voice(message: Message) -> None:
    """Handle voice messages — transcribe with Whisper then route as text."""
    from agents.voice_agent import transcribe, is_configured

    if not is_configured():
        await message.answer(
            "🎤 Голосовой ввод не настроен.\n"
            "Добавь <code>OPENAI_API_KEY=sk-...</code> в .env"
        )
        return

    await message.answer("🎤 Распознаю голос...")

    voice = message.voice or message.audio
    file_info = await message.bot.get_file(voice.file_id)
    file_bytes = await message.bot.download_file(file_info.file_path)
    audio_data = file_bytes.read() if hasattr(file_bytes, "read") else bytes(file_bytes)

    ext = "ogg" if message.voice else "mp3"
    text = await transcribe(audio_data, ext)

    if not text:
        await message.answer("Не удалось распознать голос. Попробуй ещё раз или напиши текстом.")
        return

    await message.answer(f"🎤 Распознано: <i>{text}</i>", parse_mode="HTML")

    # Route through the same free-text pipeline
    message.text = text
    await handle_free_text(message)


@router.message()
async def handle_free_text(message: Message) -> None:
    text = (message.text or message.caption or "").strip()
    if not text:
        return

    # Detect intent
    intent_result = await detect_intent(text)
    intent = intent_result.intent
    params = intent_result.params

    if intent_result.clarification:
        await message.answer(intent_result.clarification)
        return

    if intent == "update_price":
        await _handle_update_price(message, params)
    elif intent == "get_preis":
        from bot.handlers.commands import cmd_preis
        await cmd_preis(message)
    elif intent == "get_kp":
        client_name = params.get("client", "")
        message.text = f"/kp {client_name}"
        from bot.handlers.commands import cmd_kp
        await cmd_kp(message)
    elif intent == "price_query":
        product = params.get("product", "")
        await _handle_price_query(message, product)
    elif intent == "add_supplier":
        await _handle_add_supplier(message, params)
    elif intent == "add_client":
        await _handle_add_client(message, params)
    elif intent == "create_post":
        await _handle_create_post(message, params, text)
    elif intent == "price_trend":
        await _handle_price_trend(message, params)
    else:
        await _handle_general_question(message, text)


async def _handle_update_price(message: Message, params: dict) -> None:
    product = params.get("product", "")
    price_raw = params.get("price")
    supplier = params.get("supplier", "")

    if not product or not price_raw or not supplier:
        await message.answer(
            "Не хватает данных. Попробуй: «обнови треску б/г 182 рубля, Иванов»"
        )
        return

    try:
        price = Decimal(str(price_raw))
    except Exception:
        await message.answer("Не смог прочитать цену. Укажи число: «треска 182 Иванов»")
        return

    async with AsyncSessionFactory() as session:
        result = await save_supplier_price(
            session, product, price, supplier, source="manual"
        )

    matched = result["product_matched"]
    canonical = result["product"]
    resolved_supplier = result["supplier"]

    if matched:
        await message.answer(
            f"✓ Сохранено: {canonical} — {price:.0f}₽/кг у {resolved_supplier}"
        )
    else:
        await message.answer(
            f"✓ Сохранено (позиция «{product}» не распознана точно): "
            f"{price:.0f}₽/кг у {resolved_supplier}.\n"
            "Уточни название если нужно."
        )


async def _handle_add_supplier(message: Message, params: dict) -> None:
    name = (params.get("name") or "").strip()
    if not name:
        await message.answer(
            "Не указано имя поставщика.\n"
            "Формат: <code>добавь поставщика: Иванов, +7 924 111-22-33, Владивосток</code>"
        )
        return
    phone = (params.get("phone") or "").strip()
    telegram = (params.get("telegram") or "").strip()
    region = (params.get("region") or "").strip()
    if region and not region.startswith("Россия"):
        region = f"Россия, {region}"
    notes = (params.get("notes") or "").strip()
    async with AsyncSessionFactory() as session:
        s = await save_supplier(session, name=name, phone=phone, telegram=telegram,
                                region=region, notes=notes)
    contact = telegram or phone or "—"
    await message.answer(
        f"✅ Поставщик добавлен:\n"
        f"<b>{s.name}</b>\n"
        f"Контакт: {contact}\n"
        f"Регион: {s.region or '—'}"
    )


async def _handle_add_client(message: Message, params: dict) -> None:
    name = (params.get("name") or "").strip()
    if not name:
        await message.answer(
            "Не указано имя клиента.\n"
            "Формат: <code>добавь клиента: Марина, ресторан, Москва, +7 999 000-00-00</code>"
        )
        return
    client_type = (params.get("type") or params.get("client_type") or "").strip()
    city = (params.get("city") or "").strip()
    phone = (params.get("phone") or "").strip()
    notes = (params.get("notes") or "").strip()
    async with AsyncSessionFactory() as session:
        c = await save_client(session, name=name, client_type=client_type,
                              city=city, phone=phone, notes=notes)
    details = []
    if c.type:
        details.append(c.type)
    if c.city:
        details.append(c.city)
    if c.phone:
        details.append(c.phone)
    await message.answer(
        f"✅ Клиент добавлен:\n"
        f"<b>{c.name}</b>" + (f" — {', '.join(details)}" if details else "")
    )


async def _handle_create_post(message: Message, params: dict, original_text: str) -> None:
    topic = params.get("topic") or params.get("product") or original_text
    price_info = params.get("price", "")
    if price_info:
        price_info = f"{price_info} ₽/кг"
    await message.answer("✍️ Пишу пост...")
    from agents.post_agent import generate_post, save_style_example
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    post = await generate_post(topic=str(topic), price_info=str(price_info))
    # Save as neutral (score=0) first, update on feedback
    example_id = await save_style_example(post, score=0, topic=str(topic))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👍 Хорошо", callback_data=f"style:like:{example_id}"),
        InlineKeyboardButton(text="👎 Переделать", callback_data=f"style:dislike:{example_id}"),
        InlineKeyboardButton(text="✏️ Скопировать", callback_data=f"style:copy:{example_id}"),
    ]])
    await message.answer(post, reply_markup=keyboard)


async def _handle_price_trend(message: Message, params: dict) -> None:
    product = params.get("product", "")
    days = int(params.get("days", 30))
    if not product:
        await message.answer("Укажи позицию: «тренд треска» или «история горбуши за 14 дней»")
        return
    await message.answer(f"📊 Собираю данные по «{product}»...")
    from agents.trend_agent import get_price_history, format_trend_message
    async with AsyncSessionFactory() as session:
        data = await get_price_history(session, product, days=days)
    if data is None:
        await message.answer(f"Позиция «{product}» не найдена в базе.")
        return
    await message.answer(format_trend_message(data), parse_mode="HTML")


async def _handle_general_question(message: Message, text: str) -> None:
    from agents.post_agent import answer_question
    answer = await answer_question(text)
    await message.answer(answer)


async def _handle_price_query(message: Message, product: str) -> None:
    if not product:
        await message.answer("Укажи товар. Например: <code>почём треска у Иванова?</code>")
        return
    from sqlalchemy import select
    from memory.models import Product, SupplierPrice, Supplier, MyPrice
    from datetime import datetime, timedelta
    async with AsyncSessionFactory() as session:
        # find matching products by name
        products = (await session.execute(
            select(Product).where(Product.is_active == True)
        )).scalars().all()
        # fuzzy match
        from parsers.fuzzy_match import normalize_product_name
        prod_tuples = [(p.id, p.name, p.aliases or []) for p in products]
        match = normalize_product_name(product, prod_tuples)
        if not match:
            await message.answer(f"Товар «{product}» не найден в базе.")
            return
        pid = match.product_id
        pname = match.canonical_name
        cutoff = datetime.utcnow() - timedelta(hours=72)
        rows = (await session.execute(
            select(SupplierPrice, Supplier.name)
            .join(Supplier, SupplierPrice.supplier_id == Supplier.id, isouter=True)
            .where(SupplierPrice.product_id == pid, SupplierPrice.recorded_at >= cutoff)
            .order_by(SupplierPrice.price_rub)
        )).all()
        my_price_row = (await session.execute(
            select(MyPrice.price_rub).where(MyPrice.product_id == pid)
            .order_by(MyPrice.valid_from.desc()).limit(1)
        )).scalar()
    lines = [f"💰 <b>{pname}</b>"]
    if my_price_row:
        lines.append(f"Моя цена: <b>{my_price_row:.0f} ₽/кг</b>")
    if rows:
        lines.append("\nПоставщики:")
        for sp, sname in rows[:8]:
            lines.append(f"  • {sname or '—'}: {sp.price_rub:.0f} ₽/кг")
    else:
        lines.append("<i>Цен поставщиков нет (данные старше 72ч)</i>")
    await message.answer("\n".join(lines), parse_mode="HTML")
