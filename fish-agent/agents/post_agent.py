"""
PostAgent: generates social media posts about fish/prices via Claude.
"""
import logging

import anthropic

from config import settings

logger = logging.getLogger(__name__)

BASE_STYLE = """Ты — маркетолог оптовой рыбной компании «Торговый рыбный дом».
Пишешь посты для Telegram-канала и ВКонтакте.

ПРАВИЛА:
- Пиши живо, без казённых слов
- Используй факты о продукте (происхождение, обработка, польза)
- Добавляй призыв к действию (написать в ТГ, позвонить)
- Максимум 300 слов
- Эмодзи умеренно (3-5 штук)
- Не придумывай цены — если цена указана, используй её; если нет — пиши «цена по запросу»
- Контакт всегда в конце: @aleksey_fish или +7 914 326-50-50

Формат ответа: только готовый пост, без вступлений и пояснений."""


class PostGenerationError(RuntimeError):
    pass


async def _load_style_examples() -> str:
    """Load top approved posts from DB as few-shot examples."""
    try:
        from sqlalchemy import select
        from memory.db import AsyncSessionFactory
        from memory.models import StyleExample
        async with AsyncSessionFactory() as session:
            rows = (await session.execute(
                select(StyleExample)
                .where(StyleExample.feedback_score >= 1)
                .order_by(StyleExample.feedback_score.desc(), StyleExample.created_at.desc())
                .limit(5)
            )).scalars().all()
        if not rows:
            return ""
        examples = "\n---\n".join(r.content for r in rows)
        return f"\n\nПРИМЕРЫ ПОСТОВ (учитывай стиль):\n---\n{examples}\n---"
    except Exception as e:
        logger.warning("Failed to load style examples: %s", e)
        return ""


async def generate_post(topic: str, price_info: str = "") -> str:
    """Generate a social media post about a fish product or topic."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    style_block = await _load_style_examples()
    system = BASE_STYLE + style_block

    user_msg = f"Напиши пост про: {topic}"
    if price_info:
        user_msg += f"\nЦеновая информация: {price_info}"

    try:
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text.strip()
    except anthropic.APIError as e:
        logger.error("PostAgent API error")
        raise PostGenerationError("Не удалось сгенерировать пост") from e


async def save_style_example(content: str, score: int, topic: str = "") -> int:
    """Save a generated post as a style example. Returns the saved example id."""
    from sqlalchemy import select
    from memory.db import AsyncSessionFactory
    from memory.models import StyleExample
    tags = [w for w in topic.lower().split() if len(w) > 3][:5]
    async with AsyncSessionFactory() as session:
        ex = StyleExample(
            platform="telegram",
            content=content,
            tags=tags,
            feedback_score=score,
            is_original=False,
        )
        session.add(ex)
        await session.commit()
        return ex.id


async def update_style_score(example_id: int, score: int) -> None:
    """Update feedback score for a style example."""
    from memory.db import AsyncSessionFactory
    from memory.models import StyleExample
    async with AsyncSessionFactory() as session:
        ex = await session.get(StyleExample, example_id)
        if ex:
            ex.feedback_score = score
            await session.commit()


async def answer_question(question: str, context: str = "") -> str:
    """Answer a general business question using Claude."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    system = """Ты — бизнес-ассистент владельца оптовой торговли рыбой «Торговый рыбный дом».
Работаешь с рыбой и морепродуктами с Дальнего Востока (Сахалин, Камчатка, Приморье).
Отвечаешь кратко и по делу. Если вопрос не по теме рыбного бизнеса — отвечаешь всё равно полезно.
"""
    user_msg = question
    if context:
        user_msg = f"Контекст: {context}\n\nВопрос: {question}"

    try:
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text.strip()
    except anthropic.APIError as e:
        logger.error("AnswerAgent API error: %s", e)
        return f"Ошибка: {e}"
