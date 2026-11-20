"""Claude-powered content generator."""
import logging

import anthropic

from config import settings

logger = logging.getLogger(__name__)

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def generate_weekly_promo() -> str:
    from content.templates import render_weekly_promo_prompt

    prompt = render_weekly_promo_prompt(settings.company_name, settings.company_phone)
    logger.info("Generating weekly_promo via Claude")

    message = await _client.messages.create(
        model=settings.claude_model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    logger.info("weekly_promo generated (%d chars)", len(text))
    return text
