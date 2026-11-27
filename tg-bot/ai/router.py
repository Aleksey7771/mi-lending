from openai import AsyncOpenAI

import config
from ai.prompts.router_prompt import ROUTER_SYSTEM_PROMPT, VALID_INTENTS

_client = AsyncOpenAI(
    api_key=config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)


async def _llm_classify(text: str) -> str:
    response = await _client.chat.completions.create(
        model=config.ROUTER_MODEL,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=10,
    )
    return response.choices[0].message.content.strip()


async def detect_intent(text: str) -> str:
    try:
        result = await _llm_classify(text)
        return result if result in VALID_INTENTS else "OTHER"
    except Exception:
        return "OTHER"
