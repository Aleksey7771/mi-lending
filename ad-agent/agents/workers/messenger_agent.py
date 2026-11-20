"""Messenger agent — sends daily_price / weekly_promo to Telegram groups.

Rule 1 enforcement: only posts to channels present in publish_channels table.
Rule 2 enforcement: every post requires owner approve before sending.

Phase 1: Telegram groups via Telethon.
Phase 4: WhatsApp, Max.
"""
import json
import logging
import uuid
from datetime import datetime, timezone

from agents.state import AgentState

logger = logging.getLogger(__name__)


async def messenger_node(state: AgentState) -> AgentState:
    task = state["task_type"]
    logger.info("messenger_agent: task=%s", task)

    if task == "daily_price":
        return await _handle_daily_price(state)
    if task == "weekly_promo":
        return await _handle_weekly_promo(state)

    return {**state, "worker_result": {"done": True, "error": f"unknown task: {task}"}}


# ── daily_price ───────────────────────────────────────────────────────────────

async def _handle_daily_price(state: AgentState) -> AgentState:
    from approve.flow import request_approve
    from content.templates import render_daily_price
    from memory.db import async_session
    from sqlalchemy import text

    async with async_session() as session:
        rows = await session.execute(
            text(
                """
                SELECT p.name, mp.price_rub, p.unit
                FROM my_prices mp
                JOIN products p ON p.id = mp.product_id
                WHERE p.is_active = TRUE
                  AND (mp.valid_until IS NULL OR mp.valid_until > NOW())
                ORDER BY p.id
                LIMIT 10
                """
            )
        )
        prices = rows.fetchall()

    if not prices:
        logger.warning("messenger_agent: no active prices — skipping")
        return {**state, "worker_result": {"done": True, "skipped": "no_prices"}}

    text_body = render_daily_price(prices)
    channels = await _load_channels("daily_price")

    if not channels:
        logger.warning("messenger_agent: no publish_channels for daily_price — skipping")
        return {**state, "worker_result": {"done": True, "skipped": "no_channels"}}

    # Save draft to content table
    content_id = await _save_content_draft("telegram", text_body)

    approved, final_text = await request_approve(
        text=text_body,
        task_type="daily_price",
        channels=channels,
        content_id=content_id,
    )

    if not approved:
        await _update_content_status(content_id, "rejected")
        return {**state, "worker_result": {"done": True, "rejected": True}}

    await _update_content_status(content_id, "approved")
    posted, failed = await _post_to_channels(final_text, channels, content_id)
    await _update_content_status(content_id, "published")

    return {**state, "worker_result": {
        "done": True, "posted": posted, "failed": failed, "content_id": content_id,
    }}


# ── weekly_promo ──────────────────────────────────────────────────────────────

async def _handle_weekly_promo(state: AgentState) -> AgentState:
    from approve.flow import request_approve
    from content.generator import generate_weekly_promo

    text_body = state["task_payload"].get("text") or await generate_weekly_promo()
    channels = await _load_channels("weekly_promo")

    if not channels:
        logger.warning("messenger_agent: no publish_channels for weekly_promo — skipping")
        return {**state, "worker_result": {"done": True, "skipped": "no_channels"}}

    content_id = await _save_content_draft("telegram", text_body)

    approved, final_text = await request_approve(
        text=text_body,
        task_type="weekly_promo",
        channels=channels,
        content_id=content_id,
    )

    if not approved:
        await _update_content_status(content_id, "rejected")
        return {**state, "worker_result": {"done": True, "rejected": True}}

    await _update_content_status(content_id, "approved")
    posted, failed = await _post_to_channels(final_text, channels, content_id)
    await _update_content_status(content_id, "published")

    return {**state, "worker_result": {"done": True, "posted": posted, "failed": failed}}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_channels(purpose: str) -> list[dict]:
    from memory.db import async_session
    from sqlalchemy import text

    async with async_session() as session:
        rows = await session.execute(
            text(
                "SELECT platform, channel_id, display_name "
                "FROM publish_channels "
                "WHERE is_active = TRUE AND (purpose = :p OR purpose = 'any')"
            ),
            {"p": purpose},
        )
        return [
            {"platform": r.platform, "channel_id": r.channel_id, "display_name": r.display_name}
            for r in rows.fetchall()
        ]


async def _save_content_draft(platform: str, body: str) -> str:
    from memory.db import async_session
    from sqlalchemy import text

    cid = str(uuid.uuid4())
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO content (id, platform, body, status, created_at, updated_at) "
                "VALUES (:id, :platform, :body, 'pending_approval', NOW(), NOW())"
            ),
            {"id": cid, "platform": platform, "body": body},
        )
        await session.commit()
    return cid


async def _update_content_status(
    content_id: str,
    status: str,
    approved_by: int | None = None,
) -> None:
    from memory.db import async_session
    from config import settings
    from sqlalchemy import text

    extra_cols = ""
    extra_vals: dict = {}

    if status == "approved":
        extra_cols = ", approved_by_telegram_id=:by, approved_at=NOW()"
        extra_vals["by"] = approved_by or settings.owner_telegram_id
    elif status == "published":
        extra_cols = ", published_at=NOW()"

    async with async_session() as session:
        await session.execute(
            text(f"UPDATE content SET status=:s, updated_at=NOW(){extra_cols} WHERE id=:id"),
            {"s": status, "id": content_id, **extra_vals},
        )
        await session.commit()


async def _post_to_channels(
    text_body: str,
    channels: list[dict],
    content_id: str,
) -> tuple[int, int]:
    """
    Post to all Telegram channels. Returns (posted_count, failed_count).
    - Numeric IDs (personal chats / supergroups by id) → aiogram Bot API (works without Telethon session)
    - Username handles → Telethon MTProto (requires authorized session)
    Logs each attempt to ad_log.
    """
    from memory.db import async_session
    from bot.instance import bot as aiogram_bot
    from platforms.telegram_client import get_client
    from sqlalchemy import text as sql_text

    posted = failed = 0

    async with async_session() as session:
        for ch in channels:
            if ch["platform"] != "telegram":
                logger.debug("Skipping %s (Phase 4)", ch["platform"])
                continue

            action = "failed"
            error_msg: str | None = None
            meta: dict = {}
            channel_id = ch["channel_id"]

            try:
                # Use Bot API for numeric IDs, Telethon for @username handles
                if channel_id.lstrip("-").isdigit():
                    sent = await aiogram_bot.send_message(int(channel_id), text_body)
                    meta = {"tg_msg_id": sent.message_id}
                else:
                    client = await get_client()
                    msg = await client.send_message(channel_id, text_body)
                    meta = {"tg_msg_id": msg.id}
                action = "posted"
                posted += 1
                logger.info("Posted to %s — tg_msg_id=%s", channel_id, meta.get("tg_msg_id"))
            except Exception as exc:
                error_msg = str(exc)[:500]
                failed += 1
                logger.error("Failed to post to %s: %s", channel_id, exc)

            await session.execute(
                sql_text(
                    "INSERT INTO ad_log "
                    "(id, content_id, platform, target, action, error_msg, meta, created_at) "
                    "VALUES (:id, :cid::uuid, :platform, :target, :action, :err, :meta::jsonb, :ts)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "cid": content_id,
                    "platform": ch["platform"],
                    "target": ch["channel_id"],
                    "action": action,
                    "err": error_msg,
                    "meta": json.dumps(meta),
                    "ts": datetime.now(timezone.utc),
                },
            )

        await session.commit()

    return posted, failed
