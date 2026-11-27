from unittest.mock import AsyncMock, patch

import pytest

from ai.router import detect_intent


@patch("ai.router._llm_classify", new_callable=AsyncMock, return_value="POST")
async def test_post_intent(mock_llm):
    result = await detect_intent("напиши пост про горбушу")
    assert result == "POST"
    mock_llm.assert_awaited_once()


@patch("ai.router._llm_classify", new_callable=AsyncMock, return_value="CATALOG_ADD")
async def test_catalog_add_intent(mock_llm):
    result = await detect_intent("добавь товар: кета 300р опт")
    assert result == "CATALOG_ADD"


@patch("ai.router._llm_classify", new_callable=AsyncMock, return_value="PRICE")
async def test_price_intent(mock_llm):
    result = await detect_intent("отправь прайс в Max")
    assert result == "PRICE"


@patch("ai.router._llm_classify", new_callable=AsyncMock, return_value="GARBAGE")
async def test_unknown_llm_response_falls_back_to_other(mock_llm):
    result = await detect_intent("фывапролд")
    assert result == "OTHER"


@patch("ai.router._llm_classify", new_callable=AsyncMock, side_effect=Exception("API down"))
async def test_api_error_falls_back_to_other(mock_llm):
    result = await detect_intent("любой текст")
    assert result == "OTHER"


@patch("ai.router._llm_classify", new_callable=AsyncMock, return_value="KP")
async def test_kp_intent(mock_llm):
    result = await detect_intent("сделай коммерческое предложение для ресторана")
    assert result == "KP"


@patch("ai.router._llm_classify", new_callable=AsyncMock, return_value="CATALOG_UPDATE")
async def test_catalog_update_intent(mock_llm):
    result = await detect_intent("обнови цену горбуши до 260")
    assert result == "CATALOG_UPDATE"
