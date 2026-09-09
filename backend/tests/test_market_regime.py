import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.market_sessions import CompletedSession
from app.models import DailyPrice, Stock
from app.services.market_regime import classify_regime, market_regime, price_components


class RegimeComponentTests(unittest.TestCase):
    def setUp(self):
        self.end = date(2026, 9, 8)
        self.rows = [(self.end - timedelta(days=199 - index), 100 + index) for index in range(200)]

    def test_averages_and_intraday_exclusion(self):
        result = price_components(self.rows + [(self.end + timedelta(days=1), 1)], self.end)
        self.assertTrue(result["available"])
        self.assertEqual(result["close"], 299)
        self.assertEqual(result["sma50"], 274.5)
        self.assertEqual(result["sma200"], 199.5)
        self.assertEqual(result["bars"], 200)
        self.assertGreater(result["realized_volatility20_pct"], 0)

    def test_missing_stale_short_and_invalid_data_are_unavailable(self):
        for rows in ([], self.rows[:-1], self.rows[-50:], self.rows[:-1] + [(self.end, 0)]):
            with self.subTest(size=len(rows)):
                result = price_components(rows, self.end)
                self.assertFalse(result["available"])
                self.assertIsNotNone(result["reason"])

    def test_rules_cover_risk_on_neutral_risk_off_and_unknown(self):
        spy = price_components(self.rows, self.end)
        breadth = {"available": True, "above_sma50_pct": 70}
        self.assertEqual(classify_regime(spy, breadth)[0], "risk-on")
        self.assertEqual(classify_regime(spy, breadth | {"above_sma50_pct": 50})[0], "neutral")
        self.assertEqual(classify_regime(spy | {"realized_volatility20_pct": 35}, breadth)[0], "risk-off")
        self.assertEqual(classify_regime(spy | {"close": 100, "above_sma200": False}, breadth | {"above_sma50_pct": 30})[0], "risk-off")
        self.assertEqual(classify_regime(spy, breadth | {"available": False})[0], "unknown")


class RegimeDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Stock.__table__.create(self.engine)
        DailyPrice.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.day = date(2026, 9, 8)
        self.now = datetime(2026, 9, 9, 1, tzinfo=timezone.utc)
        self.universe = {f"T{i}": {"company_name": f"Test {i}"} for i in range(12)}

    def prices(self, ticker, latest=None, count=200):
        latest = latest or self.day
        self.db.add(Stock(ticker=ticker))
        self.db.flush()
        for index in range(count):
            value = Decimal(100 + index)
            self.db.add(DailyPrice(ticker=ticker, trade_date=latest - timedelta(days=count - index - 1),
                                   open=value, high=value, low=value, close=value, volume=1000))
        self.db.commit()

    def analyze(self):
        with patch("app.services.market_regime.screening_universe", return_value=self.universe), patch(
                "app.services.market_regime.latest_completed_session", return_value=CompletedSession(self.day, self.now)):
            return market_regime(self.db, self.now)

    def test_partial_coverage_excludes_stale_stocks_and_reports_denominators(self):
        self.prices("SPY")
        for ticker in list(self.universe)[:10]:
            self.prices(ticker)
        self.prices("T10", latest=self.day - timedelta(days=1))
        self.prices("T11", count=20)
        result = self.analyze()
        self.assertEqual(result["regime"], "risk-on")
        self.assertEqual(result["breadth"]["eligible_count"], 10)
        self.assertEqual(result["breadth"]["excluded_count"], 2)
        self.assertEqual(result["breadth"]["above_sma50_pct"], 100)
        self.assertEqual(result["as_of"], "2026-09-08")

    def test_no_current_spy_or_insufficient_breadth_returns_unknown(self):
        self.prices("SPY", latest=self.day - timedelta(days=1))
        for ticker in list(self.universe)[:9]:
            self.prices(ticker)
        result = self.analyze()
        self.assertEqual(result["regime"], "unknown")
        self.assertEqual(len(result["reasons"]), 2)
        self.assertFalse(result["breadth"]["available"])


if __name__ == "__main__":
    unittest.main()
