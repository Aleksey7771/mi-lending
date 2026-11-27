from unittest.mock import AsyncMock, patch, MagicMock
from contextlib import asynccontextmanager


@patch("polling.max_dialog_loop.get_updates", new_callable=AsyncMock, return_value=[])
@patch("polling.max_dialog_loop.get_pending_auto_send", new_callable=AsyncMock, return_value=[])
@patch("polling.max_dialog_loop.get_db")
async def test_loop_runs_one_cycle_no_updates(mock_get_db, mock_pending, mock_updates, bot_mock):
    @asynccontextmanager
    async def _ctx():
        yield MagicMock()
    mock_get_db.side_effect = _ctx
    from polling.max_dialog_loop import run_one_cycle
    await run_one_cycle(bot_mock, offset=0)
    mock_updates.assert_awaited_once()


@patch("polling.max_dialog_loop.get_updates", new_callable=AsyncMock, return_value=[
    {"update_id": 10, "message": {
        "body": {"text": "есть икра?"},
        "sender": {"user_id": "u123", "name": "Иван"},
        "recipient": {"chat_id": "c456"}
    }}
])
@patch("polling.max_dialog_loop.generate_dialog_response",
       new_callable=AsyncMock, return_value="Да, икра есть, 3200₽/кг")
@patch("polling.max_dialog_loop.get_public_catalog", new_callable=AsyncMock, return_value=[])
@patch("polling.max_dialog_loop.save_dialog", new_callable=AsyncMock, return_value=1)
@patch("polling.max_dialog_loop.notify_owner", new_callable=AsyncMock)
@patch("polling.max_dialog_loop.get_pending_auto_send", new_callable=AsyncMock, return_value=[])
@patch("polling.max_dialog_loop.get_db")
async def test_loop_processes_incoming_message(mock_get_db, mock_pending, mock_notify,
                                               mock_save, mock_catalog, mock_gen,
                                               mock_updates, bot_mock):
    @asynccontextmanager
    async def _ctx():
        yield MagicMock()
    mock_get_db.side_effect = _ctx
    from polling.max_dialog_loop import run_one_cycle
    new_offset = await run_one_cycle(bot_mock, offset=0)
    mock_gen.assert_awaited_once()
    mock_save.assert_awaited_once()
    mock_notify.assert_awaited_once()
    assert new_offset == 11


@patch("polling.max_dialog_loop.get_updates", new_callable=AsyncMock, return_value=[])
@patch("polling.max_dialog_loop.get_pending_auto_send", new_callable=AsyncMock,
       return_value=[{"id": 5, "client_id": "c789", "bot_response": "Да, есть", "sent": 0}])
@patch("polling.max_dialog_loop.send_message", new_callable=AsyncMock, return_value=True)
@patch("polling.max_dialog_loop.mark_sent", new_callable=AsyncMock)
@patch("polling.max_dialog_loop.get_db")
async def test_loop_auto_sends_expired_dialogs(mock_get_db, mock_mark, mock_send,
                                               mock_pending, mock_updates, bot_mock):
    @asynccontextmanager
    async def _ctx():
        yield MagicMock()
    mock_get_db.side_effect = _ctx
    from polling.max_dialog_loop import run_one_cycle
    await run_one_cycle(bot_mock, offset=0)
    mock_send.assert_awaited_once_with("c789", "Да, есть")
    mock_mark.assert_awaited_once()
