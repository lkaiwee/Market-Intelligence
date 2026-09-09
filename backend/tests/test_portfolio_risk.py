import unittest
from datetime import date, timedelta
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.risk import RiskRequest, SizeRequest
from app.database import Base
from app.models import DailyPrice, Stock
from app.models_portfolio import PortfolioPosition
from app.services.portfolio_risk import analyze_risk, average_true_range, size_position


class PositionSizingTests(unittest.TestCase):
    def test_cash_fees_and_whole_shares_bound_actual_risk(self):
        result = size_position(side="long", entry=100, stop=90, account_equity=10000,
                               risk_pct=1, max_allocation_pct=20, available_cash=505, fee_budget=10)
        self.assertEqual(result["quantity"], 4)
        self.assertEqual(result["notional"], 400)
        self.assertEqual(result["planned_loss_including_fees"], 50)
        self.assertEqual(result["limiting_constraints"], ["available cash/capital"])

    def test_short_size_and_decimal_round_down(self):
        result = size_position(side="short", entry=3, stop=4, account_equity=10,
                               risk_pct=1, max_allocation_pct=100, fractional=True)
        self.assertEqual(result["quantity"], 0.1)
        self.assertLessEqual(result["planned_loss_including_fees"], result["risk_budget"])

    def test_no_size_when_fees_consume_budget(self):
        result = size_position(side="long", entry=10, stop=9, account_equity=100,
                               risk_pct=1, max_allocation_pct=100, fee_budget=2)
        self.assertEqual(result["quantity"], 0)
        self.assertEqual(result["planned_loss_including_fees"], 0)

    def test_wrong_stop_direction_is_rejected(self):
        for side, stop in (("long", 110), ("short", 90), ("long", 100)):
            with self.subTest(side=side, stop=stop), self.assertRaises(ValueError):
                size_position(side=side, entry=100, stop=stop, account_equity=1000, risk_pct=1, max_allocation_pct=10)

    def test_nonfinite_requests_are_rejected(self):
        with self.assertRaises(ValidationError):
            RiskRequest(stops={"AAA": float("nan")})
        with self.assertRaises(ValidationError):
            SizeRequest(entry=100, stop=90, account_equity=float("inf"), risk_pct=1, max_allocation_pct=10)


class PortfolioRiskTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.day = date(2026, 9, 4)
        self.db.add_all([Stock(ticker="AAA", sector="Technology"), Stock(ticker="BBB", sector="Energy")])
        self.db.flush()
        self.db.add_all([PortfolioPosition(ticker="AAA", shares=Decimal(10), entry_price=Decimal(90)),
                         PortfolioPosition(ticker="BBB", shares=Decimal(5), entry_price=Decimal(50))])
        self.price("AAA", self.day, 100)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def price(self, ticker, day, close):
        self.db.add(DailyPrice(ticker=ticker, trade_date=day, open=close, high=close+1, low=close-1, close=close, volume=100))

    def test_missing_price_does_not_invent_account_equity_or_complete_risk(self):
        result = analyze_risk(self.db, cash=100, stops={"AAA": 95}, use_atr=False, as_of=self.day)
        self.assertIsNone(result["account_equity"])
        self.assertIsNone(result["total_planned_downside"])
        self.assertEqual(result["covered_planned_downside"], 50)
        self.assertEqual(result["unpriced_tickers"], ["BBB"])
        self.assertEqual(result["total_cost_basis"], 1150)
        self.assertEqual(result["holdings"][0]["weight_pct"], 100)

    def test_cash_and_current_prices_derive_explicit_equity(self):
        self.price("BBB", self.day, 50)
        self.db.commit()
        result = analyze_risk(self.db, cash=750, stops={"AAA": 90, "BBB": 45}, as_of=self.day)
        self.assertEqual(result["account_equity"], 2000)
        self.assertEqual(result["total_planned_downside"], 125)
        self.assertEqual(result["account_risk_pct"], 6.25)
        self.assertEqual(result["sectors"][0]["weight_pct"], 80)

    def test_future_bars_are_excluded_and_breached_stops_are_flagged(self):
        self.price("AAA", self.day + timedelta(days=1), 1000)
        self.db.commit()
        result = analyze_risk(self.db, stops={"AAA": 105}, use_atr=False, as_of=self.day)
        holding = result["holdings"][0]
        self.assertEqual(holding["current_price"], 100)
        self.assertTrue(holding["stop_reached"])
        self.assertIsNone(holding["planned_downside"])
        self.assertTrue(any("already reached" in warning for warning in result["warnings"]))

    def test_atr_requires_full_window_and_includes_gaps(self):
        bars = [DailyPrice(trade_date=self.day + timedelta(days=i), high=100, low=98, close=99) for i in range(15)]
        bars[-1].high, bars[-1].low = 111, 109
        self.assertIsNone(average_true_range(bars[:14]))
        self.assertAlmostEqual(average_true_range(bars), (13 * 2 + 12) / 14)

    def test_stop_for_unknown_holding_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze_risk(self.db, stops={"ZZZ": 50}, as_of=self.day)


if __name__ == "__main__":
    unittest.main()
