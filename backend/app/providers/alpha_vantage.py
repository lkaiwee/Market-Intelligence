import asyncio
import csv
import io
import json
import time
from datetime import date
from decimal import Decimal

import httpx

from app.core.config import get_settings
from app.providers.base import MarketDataProvider, PriceBar
from app.security import sanitize_secret


class AlphaVantageError(RuntimeError):
    pass


class AlphaVantageProvider(MarketDataProvider):
    MIN_REQUEST_INTERVAL_SECONDS = 1.2
    MAX_RATE_LIMIT_RETRIES = 3

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.alpha_vantage_api_key
        self.base_url = settings.alpha_vantage_base_url
        self._last_request_at: float | None = None

    def _safe_error(self, message: str) -> AlphaVantageError:
        return AlphaVantageError(
            sanitize_secret(message, self.api_key)
        )

    async def _wait_for_rate_limit_window(self) -> None:
        if self._last_request_at is None:
            return

        elapsed = time.monotonic() - self._last_request_at
        remaining = self.MIN_REQUEST_INTERVAL_SECONDS - elapsed

        if remaining > 0:
            await asyncio.sleep(remaining)

    @staticmethod
    def _is_rate_limit_message(message: str) -> bool:
        message = message.lower()
        return (
            "request per second" in message
            or "rate limit" in message
            or "call frequency" in message
            or "api call frequency" in message
            or "spreading out your free api requests" in message
            or "requests per day" in message
        )

    async def _request(self, params: dict) -> dict:
        last_message: str | None = None

        for attempt in range(self.MAX_RATE_LIMIT_RETRIES + 1):
            await self._wait_for_rate_limit_window()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.base_url, params=params)

            self._last_request_at = time.monotonic()

            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise self._safe_error(str(exc)) from exc

            payload = response.json()

            if "Error Message" in payload:
                raise self._safe_error(payload["Error Message"])

            message = payload.get("Note") or payload.get("Information")

            if message:
                last_message = message

                if self._is_rate_limit_message(message):
                    if attempt < self.MAX_RATE_LIMIT_RETRIES:
                        await asyncio.sleep(1.25 * (attempt + 1))
                        continue

                raise self._safe_error(message)

            if not payload:
                raise self._safe_error("Alpha Vantage returned an empty response.")

            return payload

        raise self._safe_error(
            last_message or "Alpha Vantage rate limit retry attempts were exhausted."
        )

    async def _query(self, function: str, ticker: str) -> dict:
        return await self._request(
            {
                "function": function,
                "symbol": ticker.upper(),
                "apikey": self.api_key,
            }
        )

    async def get_daily_prices(self, ticker: str) -> list[PriceBar]:
        payload = await self._request(
            {
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker.upper(),
                "outputsize": "compact",
                "apikey": self.api_key,
            }
        )

        series = payload.get("Time Series (Daily)")
        if not series:
            raise self._safe_error(
                "Alpha Vantage returned no daily time series for this ticker."
            )

        bars = []

        for day, values in series.items():
            bars.append(
                PriceBar(
                    trade_date=date.fromisoformat(day),
                    open=Decimal(values["1. open"]),
                    high=Decimal(values["2. high"]),
                    low=Decimal(values["3. low"]),
                    close=Decimal(values["4. close"]),
                    volume=Decimal(values["5. volume"]),
                )
            )

        bars.sort(key=lambda item: item.trade_date)
        return bars

    async def get_company_overview(self, ticker: str) -> dict:
        return await self._query("OVERVIEW", ticker)

    async def get_cash_flow(self, ticker: str) -> dict:
        return await self._query("CASH_FLOW", ticker)

    async def get_balance_sheet(self, ticker: str) -> dict:
        return await self._query("BALANCE_SHEET", ticker)

    async def get_earnings_calendar(self, horizon: str = "3month") -> list[dict]:
        if horizon not in {"3month", "6month", "12month"}:
            raise ValueError("horizon must be 3month, 6month, or 12month")

        params = {
            "function": "EARNINGS_CALENDAR",
            "horizon": horizon,
            "apikey": self.api_key,
        }

        last_message = None

        for attempt in range(self.MAX_RATE_LIMIT_RETRIES + 1):
            await self._wait_for_rate_limit_window()

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(self.base_url, params=params)

            self._last_request_at = time.monotonic()

            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise self._safe_error(str(exc)) from exc

            text = response.text.strip()

            if text.startswith("{"):
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = {}

                message = (
                    payload.get("Error Message")
                    or payload.get("Note")
                    or payload.get("Information")
                )

                if message:
                    last_message = message

                    if self._is_rate_limit_message(message):
                        if attempt < self.MAX_RATE_LIMIT_RETRIES:
                            await asyncio.sleep(1.25 * (attempt + 1))
                            continue

                    raise self._safe_error(message)

            if not text:
                raise self._safe_error(
                    "Alpha Vantage returned an empty earnings calendar."
                )

            rows = [dict(row) for row in csv.DictReader(io.StringIO(text))]

            if not rows:
                raise self._safe_error(
                    "Alpha Vantage returned no earnings-calendar rows."
                )

            return rows

        raise self._safe_error(
            last_message or "Alpha Vantage rate limit retry attempts were exhausted."
        )
