"""APScheduler jobs for ad-agent.

Schedule (Asia/Vladivostok, UTC+10):
  daily_price  — Mon-Fri 09:00
  weekly_promo — Friday  09:05 (5 min after daily so they don't collide)
  scout        — every 2 hours
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings

logger = logging.getLogger(__name__)


async def _run_daily_price() -> None:
    from agents.coordinator import run_task
    logger.info("scheduler: daily_price triggered")
    try:
        await run_task("daily_price", {})
    except Exception as exc:
        logger.error("scheduler: daily_price error — %s", exc, exc_info=True)


async def _run_weekly_promo() -> None:
    from agents.coordinator import run_task
    logger.info("scheduler: weekly_promo triggered")
    try:
        await run_task("weekly_promo", {})
    except Exception as exc:
        logger.error("scheduler: weekly_promo error — %s", exc, exc_info=True)


async def _run_scout() -> None:
    from agents.coordinator import run_task
    logger.info("scheduler: scout triggered")
    try:
        await run_task("scout", {})
    except Exception as exc:
        logger.error("scheduler: scout error — %s", exc, exc_info=True)


def build_scheduler() -> AsyncIOScheduler:
    tz = settings.tz
    scheduler = AsyncIOScheduler(timezone=tz)

    # Mon-Fri 09:00
    scheduler.add_job(
        _run_daily_price,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=tz),
        id="daily_price",
        name="Daily price message",
        replace_existing=True,
    )

    # Friday 09:05
    scheduler.add_job(
        _run_weekly_promo,
        CronTrigger(day_of_week="fri", hour=9, minute=5, timezone=tz),
        id="weekly_promo",
        name="Weekly promo post",
        replace_existing=True,
    )

    # Every 2 hours
    scheduler.add_job(
        _run_scout,
        CronTrigger(minute=0, hour="*/2", timezone=tz),
        id="scout",
        name="Scout competitor prices",
        replace_existing=True,
    )

    return scheduler
