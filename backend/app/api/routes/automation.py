from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, JobRun
from app.scheduler import get_scheduler_status
from app.schemas import AlertOut, JobRunOut, JobStatusOut, ManualJobResultOut
from app.services.jobs import (
    run_alert_generation_job,
    run_daily_market_job,
    run_daily_screener_job,
    run_weekly_earnings_job,
)

router = APIRouter(tags=["Automation & Alerts"])


@router.get("/jobs/status", response_model=JobStatusOut)
def jobs_status():
    return get_scheduler_status()


@router.post("/jobs/daily/run", response_model=ManualJobResultOut)
async def manual_daily_job(
    force: bool = Query(default=False),
):
    return await run_daily_market_job(force=force)


@router.post("/jobs/screener/run", response_model=ManualJobResultOut)
async def manual_screener_job(
    force_fundamentals: bool = Query(default=False),
):
    return await run_daily_screener_job(
        force_fundamentals=force_fundamentals,
    )


@router.post("/jobs/weekly-earnings/run", response_model=ManualJobResultOut)
async def manual_weekly_earnings_job():
    return await run_weekly_earnings_job()


@router.post("/jobs/alerts/run", response_model=ManualJobResultOut)
async def manual_alert_job():
    return await run_alert_generation_job()


@router.get("/jobs/history", response_model=list[JobRunOut])
def job_history(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(JobRun)
        .order_by(JobRun.started_at.desc())
        .limit(limit)
    ).all()


@router.get("/alerts", response_model=list[AlertOut])
def get_alerts(
    days: int = Query(default=7, ge=1, le=90),
    ticker: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)

    stmt = (
        select(Alert)
        .where(
            Alert.alert_date >= cutoff,
            Alert.is_active.is_(True),
        )
        .order_by(
            Alert.alert_date.desc(),
            Alert.score.desc().nullslast(),
            Alert.created_at.desc(),
        )
    )

    if ticker:
        stmt = stmt.where(Alert.ticker == ticker.upper().strip())

    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type.upper().strip())

    return db.scalars(stmt.limit(100)).all()
