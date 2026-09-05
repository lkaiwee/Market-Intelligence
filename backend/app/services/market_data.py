from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPrice, Stock
from app.providers.base import MarketDataProvider
from app.schemas import RefreshResult


async def refresh_ticker(
    db: Session,
    provider: MarketDataProvider,
    ticker: str,
) -> RefreshResult:
    ticker = ticker.upper().strip()

    stock = db.get(Stock, ticker)
    if stock is None:
        stock = Stock(ticker=ticker)
        db.add(stock)
        db.flush()

    bars = await provider.get_daily_prices(ticker)

    changed = 0

    for bar in bars:
        existing = db.scalar(
            select(DailyPrice).where(
                DailyPrice.ticker == ticker,
                DailyPrice.trade_date == bar.trade_date,
            )
        )

        if existing is None:
            db.add(
                DailyPrice(
                    ticker=ticker,
                    trade_date=bar.trade_date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
            )
        else:
            existing.open = bar.open
            existing.high = bar.high
            existing.low = bar.low
            existing.close = bar.close
            existing.volume = bar.volume

        changed += 1

    db.commit()

    newest_date = bars[-1].trade_date if bars else None

    return RefreshResult(
        ticker=ticker,
        received=len(bars),
        inserted_or_updated=changed,
        newest_date=newest_date,
    )
