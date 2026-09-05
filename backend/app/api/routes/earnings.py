from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    EarningsRefreshOut,
    EarningsUniverseItem,
    UpcomingEarningsOut,
    WeeklyEarningsOut,
)
from app.services.earnings import (
    earnings_universe,
    refresh_earnings_calendar,
    upcoming_earnings,
    weekly_earnings,
)

router = APIRouter(prefix="/earnings", tags=["Earnings"])


@router.get("/universe", response_model=list[EarningsUniverseItem])
def get_earnings_universe():
    return earnings_universe()


@router.post("/refresh", response_model=EarningsRefreshOut)
async def refresh_earnings(
    horizon: str = Query(
        default="3month",
        pattern="^(3month|6month|12month)$",
    ),
    db: Session = Depends(get_db),
):
    try:
        return await refresh_earnings_calendar(
            db=db,
            horizon=horizon,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Yahoo Finance earnings refresh failed: {exc}",
        ) from exc


@router.get("/weekly", response_model=WeeklyEarningsOut)
def get_weekly_earnings(
    week_offset: int = Query(default=0, ge=-4, le=12),
    min_impact: int = Query(default=0, ge=0, le=10),
    db: Session = Depends(get_db),
):
    return weekly_earnings(
        db=db,
        week_offset=week_offset,
        min_impact=min_impact,
    )


@router.get("/upcoming", response_model=UpcomingEarningsOut)
def get_upcoming_earnings(
    days: int = Query(default=14, ge=1, le=366),
    min_impact: int = Query(default=0, ge=0, le=10),
    db: Session = Depends(get_db),
):
    return upcoming_earnings(
        db=db,
        days=days,
        min_impact=min_impact,
    )
