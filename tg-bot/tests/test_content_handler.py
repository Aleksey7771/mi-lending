from unittest.mock import AsyncMock, MagicMock, patch

MOCK_PRODUCT = {
    "name": "Горбуша", "price_retail": 250.0,
    "price_wholesale": 185.0, "in_stock": 1,
    "category": "рыба", "origin": "Камчатка",
    "description": "жирная", "form": "б/г",
    "unit": "кг", "min_order_wholesale": 5,
    "price_vip": None,
}


@patch("handlers.content.detect_intent", new_callable=AsyncMock, return_value="POST")
@patch("handlers.content.get_product", new_callable=AsyncMock, return_value=MOCK_PRODUCT)
@patch("handlers.content.generate_post", new_callable=AsyncMock,
       return_value="Горбуша б/г | Камчатка | 185₽/кг")
async def test_post_intent_shows_preview(mock_gen, mock_get, mock_intent,
                                          message_factory):
    msg = message_factory(text="напиши пост про горбушу")
    state = AsyncMock()
    state.update = AsyncMock()
    from handlers.content import handle_text_message
    await handle_text_message(msg, state=state)
    msg.answer.assert_awaited()
    call_text = str(msg.answer.call_args)
    assert "Горбуша" in call_text


@patch("handlers.content.detect_intent", new_callable=AsyncMock, return_value="POST")
@patch("handlers.content.get_product", new_callable=AsyncMock, return_value=None)
async def test_product_not_found_sends_error(mock_get, mock_intent, message_factory):
    msg = message_factory(text="напиши пост про кальмара")
    state = AsyncMock()
    from handlers.content import handle_text_message
    await handle_text_message(msg, state=state)
    msg.answer.assert_awaited()
    call_text = str(msg.answer.call_args).lower()
    assert "не найден" in call_text or "каталог" in call_text


@patch("handlers.content.detect_intent", new_callable=AsyncMock, return_value="OTHER")
async def test_other_intent_sends_fallback(mock_intent, message_factory):
    msg = message_factory(text="что-то непонятное")
    state = AsyncMock()
    from handlers.content import handle_text_message
    await handle_text_message(msg, state=state)
    msg.answer.assert_awaited()
