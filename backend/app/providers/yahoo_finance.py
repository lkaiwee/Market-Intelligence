from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

import pandas as pd
import yfinance as yf

from app.core.config import get_settings
from app.providers.base import MarketDataProvider, PriceBar


class YahooFinanceError(RuntimeError):
    pass


class YahooFinanceProvider(MarketDataProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.history_period = settings.yahoo_history_period

    def _download_history(self, ticker: str) -> pd.DataFrame:
        data = yf.Ticker(ticker.upper()).history(
            period=self.history_period,
            interval="1d",
            auto_adjust=False,
            actions=False,
        )

        if data is None or data.empty:
            raise YahooFinanceError(
                f"Yahoo Finance returned no daily price history for {ticker.upper()}."
            )

        return data

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
