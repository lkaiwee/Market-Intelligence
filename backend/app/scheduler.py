from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.services.jobs import (
    run_daily_market_job,
    run_daily_screener_job,
    run_weekly_earnings_job,
)


settings = get_settings()

scheduler = AsyncIOScheduler(
    timezone=settings.app_timezone,
)


def start_scheduler() -> None:
    if not settings.scheduler_enabled or scheduler.running:
        return

    scheduler.add_job(
        run_daily_market_job,
        trigger="cron",
        id="daily_market",
        replace_existing=True,
        day_of_week=settings.daily_job_day_of_week,
        hour=settings.daily_job_hour,
        minute=settings.daily_job_minute,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=7200,
    )

    scheduler.add_job(
        run_daily_screener_job,
        trigger="cron",
        id="daily_screener",
        replace_existing=True,
        day_of_week=settings.screener_job_day_of_week,
        hour=settings.screener_job_hour,
        minute=settings.screener_job_minute,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=7200,
    )

    scheduler.add_job(
        run_weekly_earnings_job,
        trigger="cron",
        id="weekly_earnings",
        replace_existing=True,
        day_of_week=settings.weekly_job_day_of_week,
        hour=settings.weekly_job_hour,
        minute=settings.weekly_job_minute,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=14400,
    )

    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


def get_scheduler_status() -> dict:
    jobs = []

    if scheduler.running:
        for job in scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "next_run_time": job.next_run_time,
                }
            )

    return {
        "scheduler_enabled": settings.scheduler_enabled,
        "scheduler_running": scheduler.running,
        "timezone": settings.app_timezone,
        "daily_schedule": (
            f"{settings.daily_job_day_of_week} "
            f"{settings.daily_job_hour:02d}:{settings.daily_job_minute:02d}"
        ),
        "weekly_schedule": (
            f"{settings.weekly_job_day_of_week} "
            f"{settings.weekly_job_hour:02d}:{settings.weekly_job_minute:02d}"
        ),
        "watchlist": settings.daily_watchlist_symbols,
        "jobs": jobs,
    }
