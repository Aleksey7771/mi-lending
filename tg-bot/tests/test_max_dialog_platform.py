from unittest.mock import AsyncMock, patch, MagicMock


@patch("platforms.max_dialog._get_client")
async def test_get_updates_returns_list_on_success(mock_get_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"updates": [{"update_id": 1, "message": {}}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_get_client.return_value = mock_client
    from platforms.max_dialog import get_updates
    result = await get_updates(offset=0)
    assert isinstance(result, list)


@patch("platforms.max_dialog._get_client")
async def test_get_updates_returns_empty_on_error(mock_get_client):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("network error"))
    mock_get_client.return_value = mock_client
    from platforms.max_dialog import get_updates
    result = await get_updates(offset=0)
    assert result == []


@patch("platforms.max_dialog._get_client")
async def test_send_message_returns_true_on_200(mock_get_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_get_client.return_value = mock_client
    from platforms.max_dialog import send_message
    result = await send_message("chat123", "Привет!")
    assert result is True


@patch("platforms.max_dialog._get_client")
async def test_send_message_returns_false_on_error(mock_get_client):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("timeout"))
    mock_get_client.return_value = mock_client
    from platforms.max_dialog import send_message
    result = await send_message("chat123", "Привет!")
    assert result is False
