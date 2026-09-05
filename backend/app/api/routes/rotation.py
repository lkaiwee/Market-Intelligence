from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.providers.yahoo_finance import YahooFinanceError, YahooFinanceProvider
from app.schemas import (
    RotationRefreshOut,
    RotationReportOut,
    RotationUniverseItem,
)
from app.services.market_data import refresh_ticker
from app.services.rotation import (
    build_rotation_report,
    rotation_universe,
)

router = APIRouter(prefix="/rotation", tags=["Money Rotation"])


@router.get("/universe", response_model=list[RotationUniverseItem])
def get_rotation_universe(
    include_themes: bool = Query(default=True),
):
    return rotation_universe(include_themes=include_themes)


@router.post("/refresh", response_model=RotationRefreshOut)
async def refresh_rotation_data(
    include_themes: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    universe = rotation_universe(include_themes=include_themes)
    provider = YahooFinanceProvider()

    items = []
    succeeded = 0
    failed = 0

    for item in universe:
        ticker = item["ticker"]

        try:
            result = await refresh_ticker(
                db=db,
                provider=provider,
                ticker=ticker,
            )

            items.append(
                {
                    "ticker": ticker,
                    "status": "OK",
                    "received": result.received,
                    "newest_date": result.newest_date,
                    "detail": None,
                }
            )
            succeeded += 1

        except YahooFinanceError as exc:
            items.append(
                {
                    "ticker": ticker,
                    "status": "FAILED",
                    "received": 0,
                    "newest_date": None,
                    "detail": str(exc),
                }
            )
            failed += 1

        except Exception as exc:
            items.append(
                {
                    "ticker": ticker,
                    "status": "FAILED",
                    "received": 0,
                    "newest_date": None,
                    "detail": str(exc),
                }
            )
            failed += 1

    return {
        "requested": len(universe),
        "succeeded": succeeded,
        "failed": failed,
        "items": items,
    }


@router.get("", response_model=RotationReportOut)
def get_rotation_report(
    include_themes: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    try:
        return build_rotation_report(
            db=db,
            include_themes=include_themes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
