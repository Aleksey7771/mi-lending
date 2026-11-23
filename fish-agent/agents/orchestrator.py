"""
Orchestrator: determines user intent via OpenAI GPT-4o and routes to the right agent.
"""
import json
import logging
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — персональный бизнес-ассистент владельца оптовой торговли рыбой и морепродуктами.
Твоя задача: понять намерение пользователя и делегировать нужному специалисту.

КОНТЕКСТ БИЗНЕСА:
- Оптовая торговля свежемороженой рыбой с Дальнего Востока (Сахалин, Камчатка, Приморье)
- Работает один человек, совмещает закупки + продажи + маркетинг
- Регион работы: вся Россия, основные клиенты: рестораны, магазины, оптовики

ВОЗМОЖНЫЕ НАМЕРЕНИЯ:
- update_price: обновить цену поставщика ("треска 180 у Иванова")
- get_preis: получить PDF прайс
- get_kp: сгенерировать КП для клиента
- create_post: написать пост для соцсетей (ключевые слова: пост, напиши, текст, реклама, объявление, промо)
- price_query: узнать текущую цену по позиции
- price_trend: показать тренд/историю цен (ключевые слова: тренд, история, график, динамика, изменение, за месяц, за неделю)
- add_supplier: добавить нового поставщика
- add_client: добавить нового клиента
- general_question: другой вопрос

Отвечай ТОЛЬКО JSON (без markdown, без пояснений):
{"intent": "<намерение>", "params": {<извлечённые параметры>}, "clarification": "<вопрос если нужен или null>"}

Примеры params для update_price: {"product": "треска б/г", "price": 182, "supplier": "Иванов"}
Примеры params для get_kp: {"client": "Марина", "products": ["лосось", "треска"]}
Примеры params для add_supplier: {"name": "Козлов", "phone": "+7 924 111-22-33", "telegram": "@kozlov_fish", "region": "Сахалин"}
Примеры params для add_client: {"name": "Марина", "type": "ресторан", "city": "Новосибирск", "phone": "+7 999 000-00-00"}
Примеры params для price_query: {"product": "горбуша"}
Примеры params для create_post: {"topic": "горбуша", "price": 95}
Примеры params для price_trend: {"product": "треска", "days": 30}
"""


@dataclass
class IntentResult:
    intent: str
    params: dict = field(default_factory=dict)
    clarification: str | None = None
    raw_response: str = ""


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def detect_intent(user_message: str) -> IntentResult:
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        return IntentResult(
            intent=data.get("intent", "general_question"),
            params=data.get("params", {}),
            clarification=data.get("clarification"),
            raw_response=raw,
        )
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning("Orchestrator error: %s", e)
        return IntentResult(intent="general_question", raw_response=str(e))
