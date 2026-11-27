import aiosqlite


async def save_dialog(
    db: aiosqlite.Connection,
    platform: str,
    client_id: str,
    client_name: str,
    message: str,
    bot_response: str,
    auto_send_at: str,
) -> int:
    cursor = await db.execute(
        """INSERT INTO client_dialogs
           (platform, client_id, client_name, message, bot_response, auto_send_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (platform, client_id, client_name, message, bot_response, auto_send_at),
    )
    await db.commit()
    return cursor.lastrowid


async def get_pending_auto_send(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute(
        """SELECT * FROM client_dialogs
           WHERE sent=0 AND cancelled=0
           AND auto_send_at <= strftime('%Y-%m-%dT%H:%M:%S', 'now')"""
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def mark_sent(db: aiosqlite.Connection, dialog_id: int) -> None:
    await db.execute(
        "UPDATE client_dialogs SET sent=1 WHERE id=?", (dialog_id,)
    )
    await db.commit()


async def cancel_auto_send(db: aiosqlite.Connection, dialog_id: int) -> None:
    await db.execute(
        "UPDATE client_dialogs SET cancelled=1 WHERE id=?", (dialog_id,)
    )
    await db.commit()


async def get_dialog(db: aiosqlite.Connection, dialog_id: int) -> dict | None:
    cursor = await db.execute(
        "SELECT * FROM client_dialogs WHERE id=?", (dialog_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None
