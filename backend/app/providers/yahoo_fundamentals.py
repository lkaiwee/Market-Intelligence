from __future__ import annotations

import asyncio

import yfinance as yf

from app.services.blue_chip_universe import yahoo_symbol


class YahooFundamentalsError(RuntimeError):
    pass


class YahooFundamentalsProvider:
    @staticmethod
    def _fetch_sync(ticker: str) -> dict:
        symbol = yahoo_symbol(ticker)

        obj = yf.Ticker(symbol)

        try:
            info = obj.get_info()
        except Exception:
            info = obj.info

        if not info:
            raise YahooFundamentalsError(
                f"Yahoo Finance returned no fundamental information for {ticker}."
            )

        return info

    async def get_company_fundamentals(self, ticker: str) -> dict:
        try:
            return await asyncio.to_thread(
                self._fetch_sync,
                ticker.upper().strip(),
            )
        except YahooFundamentalsError:
            raise
        except Exception as exc:
            raise YahooFundamentalsError(
                f"Yahoo Finance fundamentals request failed for {ticker}: {exc}"
            ) from exc
