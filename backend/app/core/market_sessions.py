"""Completed sessions for the app's U.S.-listed equities and ETFs."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import exchange_calendars as xcals


CLOSE_GRACE = timedelta(minutes=15)


@dataclass(frozen=True)
class CompletedSession:
    trade_date: date
    ready_at: datetime


@lru_cache(maxsize=2)
def _calendar(year: int):
    return xcals.get_calendar(
        "XNYS", start=f"{year - 1}-01-01", end=f"{year + 1}-12-31"
    )


def latest_completed_session(now: datetime | None = None) -> CompletedSession:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    schedule = _calendar(now.year).schedule
    completed = schedule.loc[schedule["close"] <= now - CLOSE_GRACE]
    latest = completed.iloc[-1]
    return CompletedSession(
        trade_date=completed.index[-1].date(),
        ready_at=latest["close"].to_pydatetime() + CLOSE_GRACE,
    )
