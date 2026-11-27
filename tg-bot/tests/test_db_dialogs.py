from datetime import datetime, timedelta, timezone
from db.dialogs import save_dialog, get_pending_auto_send, mark_sent, cancel_auto_send, get_dialog


async def test_save_dialog_returns_id(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    dialog_id = await save_dialog(db, "max", "123", "Иван", "есть икра?", "Да, 3200₽", past)
    assert isinstance(dialog_id, int) and dialog_id > 0


async def test_get_pending_auto_send_returns_expired(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    await save_dialog(db, "max", "123", "Иван", "есть икра?", "Да, 3200₽", past)
    rows = await get_pending_auto_send(db)
    assert len(rows) == 1
    assert rows[0]["client_name"] == "Иван"


async def test_get_pending_auto_send_ignores_future(db):
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    await save_dialog(db, "max", "123", "Иван", "есть икра?", "Да, 3200₽", future)
    rows = await get_pending_auto_send(db)
    assert rows == []


async def test_mark_sent_excludes_from_pending(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    dialog_id = await save_dialog(db, "max", "123", "Иван", "?", "Ответ", past)
    await mark_sent(db, dialog_id)
    rows = await get_pending_auto_send(db)
    assert rows == []


async def test_cancel_auto_send_excludes_from_pending(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    dialog_id = await save_dialog(db, "max", "123", "Иван", "?", "Ответ", past)
    await cancel_auto_send(db, dialog_id)
    rows = await get_pending_auto_send(db)
    assert rows == []


async def test_get_dialog_returns_row(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    dialog_id = await save_dialog(db, "max", "c1", "Иван", "?", "Ответ", past)
    row = await get_dialog(db, dialog_id)
    assert row is not None
    assert row["client_name"] == "Иван"
