from openai import AsyncOpenAI

import config
from ai.prompts.dialog import build_dialog_prompt

_client = AsyncOpenAI(
    api_key=config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)


async def generate_dialog_response(
    message: str,
    catalog: list[dict],
    settings: dict,
) -> str:
    messages = build_dialog_prompt(message, catalog, settings)
    response = await _client.chat.completions.create(
        model=config.DIALOG_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()
