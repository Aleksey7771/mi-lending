import pytest
from unittest.mock import AsyncMock, patch

from ai.generator import generate_post

PRODUCT = {
    "name": "Горбуша", "category": "рыба", "form": "б/г",
    "price_retail": 250.0, "price_wholesale": 185.0, "price_vip": 160.0,
    "origin": "Камчатка", "description": "Жирная, вылов этой недели",
    "in_stock": 1, "unit": "кг", "min_order_wholesale": 5,
}


@patch("ai.generator._llm_generate", new_callable=AsyncMock,
       return_value="🐟 Горбуша б/г | Камчатка\n💰 Опт: 185₽/кг\n@manager")
async def test_generate_post_returns_string(mock_llm):
    result = await generate_post(PRODUCT, "напиши пост", style_profile=None)
    assert isinstance(result, str)
    assert len(result) > 10


@patch("ai.generator._llm_generate", new_callable=AsyncMock, return_value="пост")
async def test_generate_post_does_not_contain_vip_price(mock_llm):
    await generate_post(PRODUCT, "пост", style_profile=None)
    prompt_messages = mock_llm.call_args[0][0]
    prompt_text = str(prompt_messages)
    assert "160.0" not in prompt_text


@patch("ai.generator._llm_generate", new_callable=AsyncMock,
       side_effect=Exception("API down"))
async def test_generate_post_reraises_on_error(mock_llm):
    with pytest.raises(Exception, match="API down"):
        await generate_post(PRODUCT, "пост", style_profile=None)
