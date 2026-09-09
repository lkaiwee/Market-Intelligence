import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from sqlalchemy.dialects import postgresql

from app.core.market_sessions import CompletedSession
from app.providers import yahoo_finance
from app.providers.yahoo_finance import YahooFinanceError
from app.services import jobs, screener_refresh


SESSION = CompletedSession(
    trade_date=date(2026, 9, 8),
    ready_at=datetime(2026, 9, 8, 20, 15, tzinfo=timezone.utc),
)


def price_frame(day="2026-09-08", close=225.41):
    return pd.DataFrame(
        {"Open": [224.0], "High": [228.0], "Low": [223.0],
         "Close": [close], "Volume": [1000]},
        index=pd.DatetimeIndex([day]),
    )


class ScreenerPriceRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def run_refresh(self, tickers, data, fallback):
        db = MagicMock()
        db.get.side_effect = lambda *_: SimpleNamespace(
            company_name=None, sector=None, industry=None,
        )
        registry = {ticker: {"company_name": ticker} for ticker in tickers}
        with (
            patch.object(screener_refresh, "screening_universe", return_value=registry),
            patch.object(screener_refresh, "_download_prices_sync", return_value=data),
            patch.object(screener_refresh, "latest_completed_session", return_value=SESSION),
            patch.object(screener_refresh, "_fundamentals_stale", return_value=False),
            patch.object(screener_refresh.YahooFinanceProvider, "_download_history",
                         side_effect=fallback) as retry,
        ):
            result = await screener_refresh.refresh_blue_chip_screener(db)
        return result, db, retry

    async def job_status(self, refresh_result):
        db = MagicMock()
        with (
            patch.object(jobs, "SessionLocal", return_value=db),
            patch.object(jobs, "refresh_blue_chip_screener",
                         new=AsyncMock(return_value=refresh_result)),
            patch.object(jobs, "_start_job", return_value=MagicMock()),
            patch.object(jobs, "_finish_job") as finish,
        ):
            result = await jobs.run_daily_screener_job()
        self.assertEqual(finish.call_args.args[2], result["status"])
        return result

    async def test_only_stale_bulk_symbol_retries_and_corrected_close_is_written(self):
        data = pd.concat({
            "MRVL": price_frame("2026-09-04", 227.10),
            "NVDA": price_frame(close=180.0),
        }, axis=1)
        result, db, retry = await self.run_refresh(
            ["MRVL", "NVDA"], data, lambda _: price_frame(),
        )
        retry.assert_called_once_with("MRVL")
        self.assertEqual(result["prices_succeeded"], 2)
        self.assertEqual(result["prices_failed"], 0)
        self.assertEqual(result["expected_market_date"], "2026-09-08")
        self.assertEqual(result["newest_market_date"], "2026-09-08")
        written = [call.args[0].compile(dialect=postgresql.dialect()).params
                   for call in db.execute.call_args_list]
        self.assertEqual(written[0]["ticker_m0"], "MRVL")
        self.assertEqual(written[0]["trade_date_m0"], SESSION.trade_date)
        self.assertAlmostEqual(written[0]["close_m0"], 225.41)
        self.assertEqual(db.begin_nested.call_count, 2)
        self.assertEqual((await self.job_status(result))["status"], "SUCCESS")

    async def test_stale_fallback_cannot_write_prices_or_report_job_success(self):
        stale = price_frame("2026-09-04")
        result, db, retry = await self.run_refresh(["MRVL"], stale, lambda _: stale)
        retry.assert_called_once_with("MRVL")
        db.execute.assert_not_called()
        self.assertEqual(result["prices_succeeded"], 0)
        self.assertEqual(result["prices_failed"], 1)
        self.assertIsNone(result["newest_market_date"])
        self.assertIn("MRVL", result["price_failures"][0])
        self.assertIn("stale", result["price_failures"][0])
        status = await self.job_status(result)
        self.assertEqual(status["status"], "FAILED")
        self.assertIn("expected close 2026-09-08", status["detail"])

    async def test_failed_symbol_keeps_good_bulk_prices_and_reports_partial(self):
        data = pd.concat({
            "MRVL": price_frame("2026-09-04"),
            "NVDA": price_frame(close=180.0),
        }, axis=1)
        result, db, _ = await self.run_refresh(
            ["MRVL", "NVDA"], data, YahooFinanceError("source unavailable"),
        )
        self.assertEqual(result["prices_succeeded"], 1)
        self.assertEqual(result["prices_failed"], 1)
        self.assertEqual(db.execute.call_count, 1)
        written = db.execute.call_args.args[0].compile(dialect=postgresql.dialect()).params
        self.assertEqual(written["ticker_m0"], "NVDA")
        db.rollback.assert_not_called()
        status = await self.job_status(result)
        self.assertEqual(status["status"], "PARTIAL")
        self.assertIn("MRVL: source unavailable", status["detail"])

    async def test_missing_bulk_response_uses_individual_fallback(self):
        result, db, retry = await self.run_refresh(
            ["MRVL", "NVDA"], None, lambda _: price_frame(),
        )
        self.assertEqual(retry.call_count, 2)
        self.assertEqual(result["prices_succeeded"], 2)
        self.assertEqual(result["prices_failed"], 0)
        self.assertEqual(db.execute.call_count, 2)

    async def test_fallback_preserves_canonical_database_symbol(self):
        data = pd.concat({"BRK-B": price_frame("2026-09-04")}, axis=1)
        result, db, retry = await self.run_refresh(["BRK.B"], data, lambda _: price_frame())
        retry.assert_called_once_with("BRK-B")
        self.assertEqual(result["prices_succeeded"], 1)
        written = db.execute.call_args.args[0].compile(dialect=postgresql.dialect()).params
        self.assertEqual(written["ticker_m0"], "BRK.B")


class YahooRequestBoundsTests(unittest.TestCase):
    def test_bulk_requests_use_a_fresh_timezone_aware_end(self):
        first = datetime(2026, 9, 9, 1, 30, tzinfo=timezone.utc)
        second = first + timedelta(minutes=1)
        with (
            patch.object(screener_refresh, "datetime") as clock,
            patch.object(screener_refresh.yf, "download", return_value=price_frame()) as download,
        ):
            clock.now.side_effect = [first, second]
            screener_refresh._download_prices_sync(["MRVL"], "2y")
            screener_refresh._download_prices_sync(["MRVL"], "2y")
        for call, expected_end in zip(download.call_args_list, [first, second]):
            self.assertEqual(call.kwargs["end"], expected_end)
            self.assertEqual(call.kwargs["period"], "2y")
            self.assertFalse(call.kwargs["auto_adjust"])
            self.assertEqual(call.kwargs["interval"], "1d")

    def test_single_ticker_uses_fresh_bounds_and_excludes_unfinished_bar(self):
        now = datetime(2026, 9, 9, 19, 0, tzinfo=timezone.utc)
        data = pd.concat([price_frame(), price_frame("2026-09-09", 999.0)])
        provider = yahoo_finance.YahooFinanceProvider()
        with (
            patch.object(yahoo_finance, "datetime") as clock,
            patch.object(yahoo_finance, "latest_completed_session", return_value=SESSION),
            patch.object(yahoo_finance.yf, "Ticker") as ticker,
        ):
            clock.now.return_value = now
            ticker.return_value.history.return_value = data
            result = provider._download_history("MRVL")
        self.assertEqual(ticker.return_value.history.call_args.kwargs["end"], now)
        self.assertEqual(list(result.index.date), [SESSION.trade_date])
        self.assertAlmostEqual(result.iloc[-1]["Close"], 225.41)


if __name__ == "__main__":
    unittest.main()
