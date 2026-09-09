from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
import numpy as np
import yfinance as yf

from app.core.config import get_settings
from app.core.market_sessions import CompletedSession, latest_completed_session
from app.providers.base import MarketDataProvider, PriceBar


class YahooFinanceError(RuntimeError):
    pass


def completed_price_frame(
    data: pd.DataFrame, ticker: str, session: CompletedSession
) -> pd.DataFrame:
    required = {"Open", "High", "Low", "Close", "Volume"}
    if data is None or data.empty or not required.issubset(data.columns):
        raise YahooFinanceError(f"Yahoo Finance returned no usable daily history for {ticker}.")
    frame = data.loc[[pd.Timestamp(ts).date() <= session.trade_date for ts in data.index]].copy()
    # An unfinished or missing OHLC row must never count as a completed close.
    ohlc = frame[["Open", "High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce")
    frame = frame.loc[np.isfinite(ohlc).all(axis=1)].sort_index()
    newest = pd.Timestamp(frame.index[-1]).date() if not frame.empty else None
    if newest != session.trade_date:
        raise YahooFinanceError(
            f"Yahoo Finance prices for {ticker} are stale: newest {newest}; "
            f"expected completed U.S. session {session.trade_date}. Retry the refresh."
        )
    return frame


class YahooFinanceProvider(MarketDataProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.history_period = settings.yahoo_history_period

    def _download_history(self, ticker: str) -> pd.DataFrame:
        data = yf.Ticker(ticker.upper()).history(
            period=self.history_period,
            # Vary the time bounds so a cached range response cannot freeze today's close.
            end=datetime.now(timezone.utc),
            interval="1d",
            auto_adjust=False,
            actions=False,
        )

        if data is None or data.empty:
            raise YahooFinanceError(
                f"Yahoo Finance returned no daily price history for {ticker.upper()}."
            )

        return completed_price_frame(data, ticker, latest_completed_session())

    async def get_daily_prices(self, ticker: str) -> list[PriceBar]:
        ticker = ticker.upper().strip()

        try:
            data = await asyncio.to_thread(
                self._download_history,
                ticker,
            )
        except YahooFinanceError:
            raise
        except Exception as exc:
            raise YahooFinanceError(
                f"Yahoo Finance request failed for {ticker}: {exc}"
            ) from exc

        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required.difference(data.columns)

        if missing:
            raise YahooFinanceError(
                f"Yahoo Finance response for {ticker} is missing columns: "
                f"{', '.join(sorted(missing))}."
            )

        bars: list[PriceBar] = []

        for timestamp, row in data.iterrows():
            if pd.isna(row["Open"]) or pd.isna(row["Close"]):
                continue

            trade_date = timestamp.date()

            volume = row["Volume"]
            if pd.isna(volume):
                volume = 0

            bars.append(
                PriceBar(
                    trade_date=trade_date,
                    open=Decimal(str(float(row["Open"]))),
                    high=Decimal(str(float(row["High"]))),
                    low=Decimal(str(float(row["Low"]))),
                    close=Decimal(str(float(row["Close"]))),
                    volume=Decimal(str(int(volume))),
                )
            )

        if not bars:
            raise YahooFinanceError(
                f"Yahoo Finance returned no usable daily bars for {ticker}."
            )

        bars.sort(key=lambda item: item.trade_date)
        return bars
