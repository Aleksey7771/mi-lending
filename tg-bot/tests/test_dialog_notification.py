from unittest.mock import AsyncMock, MagicMock, patch


async def test_notify_owner_sends_message(bot_mock):
    bot_mock.send_message = AsyncMock()
    from handlers.dialog_notification import notify_owner
    await notify_owner(bot_mock, dialog_id=1, client_name="Иван",
                       question="есть икра?", bot_response="Да, 3200₽/кг")
    bot_mock.send_message.assert_awaited_once()
    call_text = str(bot_mock.send_message.call_args)
    assert "Иван" in call_text
    assert "есть икра?" in call_text


@patch("handlers.dialog_notification.cancel_auto_send", new_callable=AsyncMock)
async def test_rewrite_callback_cancels_auto_send(mock_cancel, bot_mock):
    callback = MagicMock()
    callback.data = "dialog_rewrite_42"
    callback.bot = bot_mock
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.answer = AsyncMock()
    state = AsyncMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    from handlers.dialog_notification import handle_dialog_rewrite
    await handle_dialog_rewrite(callback, state=state)
    mock_cancel.assert_awaited()


@patch("handlers.dialog_notification.mark_sent", new_callable=AsyncMock)
@patch("handlers.dialog_notification.send_message", new_callable=AsyncMock, return_value=True)
async def test_ok_callback_sends_immediately(mock_send, mock_mark, bot_mock):
    callback = MagicMock()
    callback.data = "dialog_ok_7"
    callback.bot = bot_mock
    callback.message = MagicMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    from handlers.dialog_notification import handle_dialog_ok
    with patch("handlers.dialog_notification.get_dialog",
               new_callable=AsyncMock,
               return_value={"id": 7, "client_id": "chat_abc", "bot_response": "Да, есть",
                             "sent": 0, "cancelled": 0}):
        await handle_dialog_ok(callback)
    mock_send.assert_awaited_once_with("chat_abc", "Да, есть")
    mock_mark.assert_awaited_once()
