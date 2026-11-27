from openai import AsyncOpenAI

import config
from ai.prompts.post import build_post_prompt

_client = AsyncOpenAI(
    api_key=config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)


async def _llm_generate(messages: list[dict]) -> str:
    response = await _client.chat.completions.create(
        model=config.CONTENT_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


async def generate_post(
    product: dict,
    command: str,
    style_profile: dict | None = None,
) -> str:
    messages = build_post_prompt(product, command, style_profile)
    return await _llm_generate(messages)
