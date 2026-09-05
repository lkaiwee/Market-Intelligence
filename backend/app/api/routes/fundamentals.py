from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FundamentalSnapshot, Stock
from app.providers.alpha_vantage import AlphaVantageError, AlphaVantageProvider
from app.schemas import FundamentalOut, FundamentalRefreshOut
from app.services.fundamentals import refresh_fundamentals, serialize_fundamentals

router = APIRouter(prefix="/stocks", tags=["Fundamentals"])


@router.post("/{ticker}/fundamentals/refresh", response_model=FundamentalRefreshOut)
async def refresh_stock_fundamentals(
    ticker: str,
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()

    try:
        snapshot = await refresh_fundamentals(
            db=db,
            provider=AlphaVantageProvider(),
            ticker=ticker,
        )
    except AlphaVantageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh fundamentals for {ticker}: {exc}",
        ) from exc

    stock = db.get(Stock, ticker)

    return {
        "ticker": ticker,
        "company_name": stock.company_name if stock else None,
        "sector": stock.sector if stock else None,
        "industry": stock.industry if stock else None,
        "updated_at": snapshot.updated_at,
    }


@router.get("/{ticker}/fundamentals", response_model=FundamentalOut)
def get_stock_fundamentals(
    ticker: str,
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()

    stock = db.get(Stock, ticker)
    snapshot = db.get(FundamentalSnapshot, ticker)

    if stock is None or snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No stored fundamentals for {ticker}. Run "
                f"POST /api/stocks/{ticker}/fundamentals/refresh first."
            ),
        )

    return serialize_fundamentals(stock, snapshot)
