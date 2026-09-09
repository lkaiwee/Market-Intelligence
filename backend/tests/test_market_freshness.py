import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pandas as pd

from app.core.market_sessions import CompletedSession, latest_completed_session
from app.models import MarketRefreshState
from app.providers.yahoo_finance import YahooFinanceError, completed_price_frame
from app.services import jobs


UTC = timezone.utc


class CompletedSessionTests(unittest.TestCase):
    def test_labor_day_and_weekend_keep_the_last_real_trading_session(self):
        for now, expected in (
            (datetime(2026, 9, 7, 23, tzinfo=UTC), date(2026, 9, 4)),
            (datetime(2026, 9, 8, 19, tzinfo=UTC), date(2026, 9, 4)),
            (datetime(2026, 9, 12, 12, tzinfo=UTC), date(2026, 9, 11)),
        ):
            with self.subTest(now=now):
                self.assertEqual(latest_completed_session(now).trade_date, expected)

    def test_close_is_not_ready_until_the_provider_grace_period_ends(self):
        ready_at = datetime(2026, 9, 8, 20, 15, tzinfo=UTC)
        for now in (ready_at - timedelta(minutes=15), ready_at - timedelta(seconds=1)):
            with self.subTest(now=now):
                self.assertEqual(latest_completed_session(now).trade_date, date(2026, 9, 4))

        session = latest_completed_session(ready_at)
        self.assertEqual(session.trade_date, date(2026, 9, 8))
        self.assertEqual(session.ready_at, ready_at)

    def test_dst_changes_the_utc_close_time(self):
        for day, ready_hour in (
            (date(2026, 3, 6), 21),
            (date(2026, 3, 9), 20),
            (date(2026, 10, 30), 20),
            (date(2026, 11, 2), 21),
        ):
            ready_at = datetime(day.year, day.month, day.day, ready_hour, 15, tzinfo=UTC)
            with self.subTest(day=day):
                self.assertNotEqual(
                    latest_completed_session(ready_at - timedelta(seconds=1)).trade_date,
                    day,
                )
                session = latest_completed_session(ready_at)
                self.assertEqual(session.trade_date, day)
                self.assertEqual(session.ready_at, ready_at)

    def test_thanksgiving_early_close_is_ready_at_1815_utc(self):
        ready_at = datetime(2026, 11, 27, 18, 15, tzinfo=UTC)
        self.assertEqual(
            latest_completed_session(ready_at - timedelta(seconds=1)).trade_date,
            date(2026, 11, 25),
        )
        session = latest_completed_session(ready_at)
        self.assertEqual(session.trade_date, date(2026, 11, 27))
        self.assertEqual(session.ready_at, ready_at)

    def test_singapore_calendar_day_does_not_become_the_market_session_date(self):
        now = datetime(2026, 9, 9, 4, 15, tzinfo=ZoneInfo("Asia/Singapore"))
        session = latest_completed_session(now)
        self.assertEqual(session.trade_date, date(2026, 9, 8))
        self.assertEqual(session.ready_at, datetime(2026, 9, 8, 20, 15, tzinfo=UTC))


class RefreshRetryTests(unittest.TestCase):
    def setUp(self):
        self.session = CompletedSession(
            trade_date=date(2026, 9, 8),
            ready_at=datetime(2026, 9, 8, 20, 15, tzinfo=UTC),
        )
        self.state = MarketRefreshState(
            ticker="MRVL",
            last_attempt_date=date(2026, 9, 9),
            status="SUCCESS",
            newest_market_date=self.session.trade_date,
            updated_at=self.session.ready_at + timedelta(minutes=20),
        )
        self.db = Mock()
        self.db.get.return_value = self.state
        completed = patch.object(jobs, "latest_completed_session", return_value=self.session)
        today = patch.object(jobs, "_local_today", return_value=date(2026, 9, 9))
        completed.start()
        today.start()
        self.addCleanup(completed.stop)
        self.addCleanup(today.stop)

    def test_failed_or_incomplete_attempts_can_retry_on_the_same_day(self):
        for status in ("FAILED", "PARTIAL", "RUNNING"):
            with self.subTest(status=status):
                self.state.status = status
                self.assertFalse(jobs._already_attempted_today(self.db, "MRVL"))

    def test_old_or_missing_market_date_can_retry_despite_success_status(self):
        for newest in (date(2026, 9, 4), None):
            with self.subTest(newest=newest):
                self.state.newest_market_date = newest
                self.assertFalse(jobs._already_attempted_today(self.db, "MRVL"))

    def test_intraday_bar_with_correct_date_does_not_block_the_final_close(self):
        self.state.updated_at = self.session.ready_at - timedelta(seconds=1)
        self.assertFalse(jobs._already_attempted_today(self.db, "MRVL"))

    def test_only_successful_current_close_from_today_is_skipped(self):
        self.assertTrue(jobs._already_attempted_today(self.db, "MRVL"))
        self.db.get.assert_called_once_with(MarketRefreshState, "MRVL")
        self.state.last_attempt_date = date(2026, 9, 8)
        self.assertFalse(jobs._already_attempted_today(self.db, "MRVL"))

    def test_legacy_naive_timestamps_are_interpreted_as_utc(self):
        self.state.updated_at = self.session.ready_at.replace(tzinfo=None)
        self.assertTrue(jobs._already_attempted_today(self.db, "MRVL"))
        self.state.updated_at -= timedelta(seconds=1)
        self.assertFalse(jobs._already_attempted_today(self.db, "MRVL"))

    def test_new_ticker_is_never_skipped(self):
        self.db.get.return_value = None
        self.assertFalse(jobs._already_attempted_today(self.db, "MRVL"))


class CompletedPriceFrameTests(unittest.TestCase):
    def setUp(self):
        self.session = CompletedSession(
            trade_date=date(2026, 9, 8),
            ready_at=datetime(2026, 9, 8, 20, 15, tzinfo=UTC),
        )
        self.frame = pd.DataFrame(
            {
                "Open": [220.0, 228.0, 226.0],
                "High": [225.0, 230.0, 232.0],
                "Low": [218.0, 224.0, 224.0],
                "Close": [223.55, 225.41, 229.80],
                "Volume": [20_000_000, 20_554_100, 1_000_000],
            },
            index=pd.DatetimeIndex(
                ["2026-09-04", "2026-09-08", "2026-09-09"],
                tz="America/New_York",
            ),
        )

    def test_unfinished_session_is_excluded_from_the_latest_close(self):
        result = completed_price_frame(self.frame, "MRVL", self.session)
        self.assertEqual(list(result.index.date), [date(2026, 9, 4), date(2026, 9, 8)])
        self.assertEqual(result.iloc[-1]["Close"], 225.41)
        self.assertEqual(len(self.frame), 3)

    def test_old_nonempty_response_cannot_be_reported_as_a_successful_refresh(self):
        with self.assertRaises(YahooFinanceError):
            completed_price_frame(self.frame.iloc[:1], "MRVL", self.session)

    def test_incomplete_latest_ohlc_is_stale_even_when_the_date_is_present(self):
        for column in ("Open", "High", "Low", "Close"):
            with self.subTest(column=column):
                frame = self.frame.copy()
                frame.loc[frame.index[1], column] = float("nan")
                with self.assertRaises(YahooFinanceError):
                    completed_price_frame(frame, "MRVL", self.session)

    def test_valid_latest_bar_can_follow_an_unusable_older_bar(self):
        self.frame.loc[self.frame.index[0], "High"] = float("nan")
        result = completed_price_frame(self.frame, "MRVL", self.session)
        self.assertEqual(list(result.index.date), [date(2026, 9, 8)])

    def test_empty_future_only_or_malformed_response_is_rejected(self):
        for frame in (
            self.frame.iloc[:0],
            self.frame.iloc[2:],
            self.frame.drop(columns=["Close"]),
        ):
            with self.subTest(shape=frame.shape, columns=list(frame.columns)):
                with self.assertRaises(YahooFinanceError):
                    completed_price_frame(frame, "MRVL", self.session)


if __name__ == "__main__":
    unittest.main()
