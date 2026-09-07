from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import DailyPrice, FundamentalSnapshot, Stock
from app.providers.yahoo_fundamentals import (
    YahooFundamentalsError,
    YahooFundamentalsProvider,
)
from app.services.blue_chip_universe import yahoo_symbol
from app.services.universe_registry import screening_universe
from app.services.yahoo_fundamentals import refresh_yahoo_fundamentals


def _extract_ticker_frame(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not isinstance(data.columns, pd.MultiIndex):
        return data.copy()

    level0 = set(str(value) for value in data.columns.get_level_values(0))
    level1 = set(str(value) for value in data.columns.get_level_values(1))

    if symbol in level0:
        return data[symbol].copy()

    if symbol in level1:
        return data.xs(symbol, axis=1, level=1).copy()

    return pd.DataFrame()


def _upsert_prices(
    db: Session,
    ticker: str,
    frame: pd.DataFrame,
) -> tuple[int, object | None]:
    if frame.empty:
        return 0, None

    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(set(frame.columns)):
        return 0, None

    records = []

    for timestamp, row in frame.iterrows():
        if pd.isna(row["Close"]) or pd.isna(row["Open"]):
            continue

        trade_date = pd.Timestamp(timestamp).date()

        records.append(
            {
                "ticker": ticker,
                "trade_date": trade_date,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(0 if pd.isna(row["Volume"]) else row["Volume"]),
            }
        )

    if not records:
        return 0, None

    stmt = pg_insert(DailyPrice).values(records)

    stmt = stmt.on_conflict_do_update(
        constraint="uq_daily_price_ticker_date",
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
        },
    )

    db.execute(stmt)

    newest = max(record["trade_date"] for record in records)
    return len(records), newest


def _download_prices_sync(symbols: list[str], period: str) -> pd.DataFrame:
    return yf.download(
        tickers=symbols,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        actions=False,
        threads=True,
        progress=False,
    )


def _fundamentals_stale(
    snapshot: FundamentalSnapshot | None,
    max_age_days: int,
) -> bool:
    if snapshot is None or snapshot.updated_at is None:
        return True

    updated = snapshot.updated_at

    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    return updated < datetime.now(timezone.utc) - timedelta(days=max_age_days)


async def refresh_blue_chip_screener(
    db: Session,
    *,
    force_fundamentals: bool = False,
    fundamentals_max_age_days: int = 7,
) -> dict:
    settings = get_settings()

    registry = screening_universe(db)
    tickers = list(registry.keys())
    yahoo_symbols = [yahoo_symbol(ticker) for ticker in tickers]

    for ticker, item in registry.items():
        stock = db.get(Stock, ticker)

        if stock is None:
            stock = Stock(
                ticker=ticker,
                company_name=item.get("company_name"),
                sector=item.get("sector"),
                industry=item.get("industry"),
            )
            db.add(stock)
        else:
            stock.company_name = stock.company_name or item.get("company_name")
            stock.sector = stock.sector or item.get("sector")
            stock.industry = stock.industry or item.get("industry")

    db.commit()

    price_data = await asyncio.to_thread(
        _download_prices_sync,
        yahoo_symbols,
        settings.yahoo_history_period,
    )

    prices_succeeded = 0
    prices_failed = []
    total_price_rows = 0
    newest_dates = {}

    for ticker in tickers:
        symbol = yahoo_symbol(ticker)
        frame = _extract_ticker_frame(price_data, symbol)

        rows, newest = _upsert_prices(db, ticker, frame)

        if rows:
            prices_succeeded += 1
            total_price_rows += rows
            newest_dates[ticker] = newest
        else:
            prices_failed.append(ticker)

    db.commit()

    provider = YahooFundamentalsProvider()

    fundamental_succeeded = 0
    fundamental_skipped = 0
    fundamental_failed = []

    for ticker in tickers:
        snapshot = db.get(FundamentalSnapshot, ticker)

        needs_refresh = (
            force_fundamentals
            or _fundamentals_stale(snapshot, fundamentals_max_age_days)
        )

        if not needs_refresh:
            fundamental_skipped += 1
            continue

        try:
            await refresh_yahoo_fundamentals(
                db=db,
                provider=provider,
                ticker=ticker,
            )
            fundamental_succeeded += 1
            await asyncio.sleep(0.15)

        except YahooFundamentalsError as exc:
            fundamental_failed.append(f"{ticker}: {exc}")

        except Exception as exc:
            fundamental_failed.append(f"{ticker}: {exc}")

    return {
        "universe_size": len(tickers),
        "prices_succeeded": prices_succeeded,
        "prices_failed": len(prices_failed),
        "price_rows_processed": total_price_rows,
        "price_failures": prices_failed,
        "fundamentals_refreshed": fundamental_succeeded,
        "fundamentals_skipped_fresh": fundamental_skipped,
        "fundamentals_failed": len(fundamental_failed),
        "fundamental_failures": fundamental_failed[:20],
        "newest_market_date": (
            max(newest_dates.values()).isoformat()
            if newest_dates
            else None
        ),
    }
