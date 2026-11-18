import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot

from config import settings
from scheduler.tasks.email_check import run_email_check
from scheduler.tasks.morning_digest import send_morning_digest
from scheduler.tasks.price_update import run_parsers, run_fishery_parser

logger = logging.getLogger(__name__)


async def _run_enrichment():
    try:
        from scripts.enrich_suppliers import run_enrichment
        updated = await run_enrichment(limit=50)  # по 50 в день чтобы не банили
        logger.info("Enrich suppliers: updated %d", updated)
    except Exception:
        logger.exception("Enrich suppliers failed")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    # Price update every hour
    scheduler.add_job(
        run_parsers,
        trigger=IntervalTrigger(minutes=settings.parser_interval_minutes),
        id="price_update",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Morning digest at configured hour in Vladivostok timezone
    scheduler.add_job(
        send_morning_digest,
        trigger=CronTrigger(
            hour=settings.morning_digest_hour,
            minute=0,
            timezone=settings.morning_digest_tz,
        ),
        kwargs={"bot": bot, "owner_id": settings.owner_telegram_id},
        id="morning_digest",
        replace_existing=True,
    )

    # Email inbox check every 15 minutes
    scheduler.add_job(
        run_email_check,
        trigger=IntervalTrigger(minutes=15),
        kwargs={"bot": bot, "owner_id": settings.owner_telegram_id},
        id="email_check",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # fishery.ru — every 2 hours (files update less often)
    scheduler.add_job(
        run_fishery_parser,
        trigger=IntervalTrigger(hours=2),
        id="fishery_update",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Enrichment of supplier contacts — daily at 03:00 Vladivostok
    scheduler.add_job(
        _run_enrichment,
        trigger=CronTrigger(hour=3, minute=0, timezone=settings.morning_digest_tz),
        id="enrich_suppliers",
        replace_existing=True,
    )

    logger.info(
        "Scheduler ready: price_update every %d min, morning_digest at %d:00 %s",
        settings.parser_interval_minutes,
        settings.morning_digest_hour,
        settings.morning_digest_tz,
    )
    return scheduler
