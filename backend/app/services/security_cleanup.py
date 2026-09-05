from sqlalchemy import select

from app.core.config import get_settings
from app.database import SessionLocal
from app.models import JobRun, MarketRefreshState
from app.security import sanitize_secret


def sanitize_persisted_secrets() -> None:
    settings = get_settings()
    secret = settings.alpha_vantage_api_key

    if not secret:
        return

    db = SessionLocal()

    try:
        changed = False

        job_runs = db.scalars(
            select(JobRun).where(JobRun.detail.is_not(None))
        ).all()

        for run in job_runs:
            safe = sanitize_secret(run.detail, secret)
            if safe != run.detail:
                run.detail = safe
                changed = True

        refresh_states = db.scalars(
            select(MarketRefreshState).where(
                MarketRefreshState.detail.is_not(None)
            )
        ).all()

        for state in refresh_states:
            safe = sanitize_secret(state.detail, secret)
            if safe != state.detail:
                state.detail = safe
                changed = True

        if changed:
            db.commit()

    finally:
        db.close()
