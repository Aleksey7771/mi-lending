from unittest.mock import AsyncMock, MagicMock, patch


async def test_telegram_publish_calls_send_message(bot_mock):
    from platforms.telegram_channel import publish_post
    bot_mock.send_message = AsyncMock(return_value=MagicMock())
    result = await publish_post(bot_mock, "Тест пост", photo_file_id=None)
    assert result is True
    bot_mock.send_message.assert_awaited_once()


async def test_telegram_publish_with_photo_calls_send_photo(bot_mock):
    from platforms.telegram_channel import publish_post
    bot_mock.send_photo = AsyncMock(return_value=MagicMock())
    result = await publish_post(bot_mock, "Тест пост", photo_file_id="AgACBAA")
    assert result is True
    bot_mock.send_photo.assert_awaited_once()


async def test_telegram_publish_returns_false_on_error(bot_mock):
    from platforms.telegram_channel import publish_post
    bot_mock.send_message = AsyncMock(side_effect=Exception("TG error"))
    result = await publish_post(bot_mock, "Тест", photo_file_id=None)
    assert result is False


@patch("platforms.max_content.httpx.AsyncClient")
async def test_max_publish_posts_to_api(mock_client_cls):
    from platforms.max_content import publish_post as max_publish
    mock_resp = MagicMock(status_code=200)
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await max_publish("Тест пост", photo_url=None)
    assert result is True


@patch("platforms.max_content.httpx.AsyncClient")
async def test_max_publish_returns_false_on_http_error(mock_client_cls):
    from platforms.max_content import publish_post as max_publish
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=Exception("timeout"))
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await max_publish("Тест пост", photo_url=None)
    assert result is False
