import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.journal import TradeInput, router as journal_router
from app.api.routes.risk import SizeRequest
from app.database import Base, get_db
from app.services.portfolio_risk import analyze_risk, size_position
from app.services.portfolio_stress import historical_risk, pair_statistics, return_frame


class SizingTests(unittest.TestCase):
    def size(self, **kwargs):
        values = dict(side="long", entry=100, stop=95, account_equity=10000, risk_pct=1,
                      max_allocation_pct=30, available_cash=10000)
        values.update(kwargs)
        return size_position(**values)

    def test_risk_cash_and_allocation_limits(self):
        result = self.size()
        self.assertEqual(result["quantity"], 20)
        self.assertEqual(result["planned_loss_including_fees"], 100)
        self.assertEqual(self.size(available_cash=550)["quantity"], 5)
        self.assertEqual(self.size(max_allocation_pct=5)["quantity"], 5)

    def test_fees_and_fractional_round_down(self):
        result = self.size(fee_budget=3, fractional=True)
        self.assertAlmostEqual(result["quantity"], 19.4)
        self.assertLessEqual(result["planned_loss_including_fees"], 100)
        self.assertEqual(self.size(fee_budget=101)["quantity"], 0)

    def test_short_stop_and_bad_precision_are_validated(self):
        self.assertEqual(self.size(side="short", stop=105)["quantity"], 20)
        for kwargs in [{"stop": 101}, {"side": "short", "stop": 95}, {"entry": 1e-20, "stop": 5e-21}]:
            with self.assertRaises(ValueError):
                self.size(**kwargs)
        with self.assertRaises(ValidationError):
            SizeRequest(entry=1e-20, stop=5e-21, account_equity=1e15, risk_pct=1, max_allocation_pct=100)

    def test_breached_stop_does_not_report_zero_total_risk(self):
        holding = dict(ticker="TEST", sector="Tech", shares=10, entry_price=110, cost_basis=1100,
                       latest_date=date(2026, 9, 8), current_price=100, market_value=1000, prices=[])
        with patch("app.services.portfolio_risk.holding_data", return_value=[holding]):
            result = analyze_risk(None, account_equity=2000, stops={"TEST": 105}, as_of=date(2026, 9, 8))
        self.assertTrue(result["holdings"][0]["stop_reached"])
        self.assertIsNone(result["total_planned_downside"])
        self.assertIsNone(result["account_risk_pct"])
        self.assertEqual(result["risk_coverage_count"], 0)

    def test_concentration_uses_priced_value_and_equity_is_not_invented(self):
        holdings = [dict(ticker=t, sector="Tech", shares=10, entry_price=10, cost_basis=100,
                         latest_date=date(2026, 9, 8), current_price=v/10, market_value=v, prices=[])
                    for t, v in [("A", 750), ("B", 250)]]
        with patch("app.services.portfolio_risk.holding_data", return_value=holdings):
            result = analyze_risk(None, use_atr=False, as_of=date(2026, 9, 8))
        self.assertEqual(result["largest_position_pct"], 75)
        self.assertAlmostEqual(result["concentration_hhi"], .625)
        self.assertIsNone(result["account_equity"])


class StressTests(unittest.TestCase):
    def test_missing_close_does_not_create_multi_session_daily_return(self):
        series = {"TEST": {date(2026, 9, 1): 100, date(2026, 9, 3): 110, date(2026, 9, 4): 121}}
        returns = return_frame(series, date(2026, 9, 4), 60)
        self.assertTrue(pd.isna(returns.loc["2026-09-03", "TEST"]))
        self.assertAlmostEqual(returns.loc["2026-09-04", "TEST"], .1)

    def test_correlation_beta_and_minimum_coverage(self):
        x = np.sin(np.arange(100)) / 100
        frame = pd.DataFrame({"SPY": x, "A": 2*x, "B": -x})
        self.assertAlmostEqual(pair_statistics(frame, "A", "SPY")["beta"], 2)
        self.assertAlmostEqual(pair_statistics(frame, "A", "B")["correlation"], -1)
        self.assertIsNone(pair_statistics(frame.iloc[:59], "A", "SPY")["beta"])

    def test_var_expected_shortfall_and_cash_scaled_risk(self):
        values = pd.Series(np.linspace(-.1, .1, 100), index=pd.date_range("2025-01-01", periods=100))
        result = historical_risk(values, 10000, .95)
        self.assertAlmostEqual(result["one_day_var_amount"], 900)
        self.assertGreaterEqual(result["one_day_expected_shortfall_amount"], result["one_day_var_amount"])
        self.assertIsNone(historical_risk(values[:59], 10000, .95))
        scaled = historical_risk(values * .5, 20000, .95)
        self.assertAlmostEqual(scaled["one_day_var_amount"], result["one_day_var_amount"])


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        app = FastAPI(); app.include_router(journal_router)
        def database():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.payload = dict(ticker="TEST", side="long", entry_date="2025-01-01", entry_price="100",
                            quantity="10", exit_date="2025-01-05", exit_price="110", fees="2", initial_stop="95", tags=["Trend"])

    def tearDown(self):
        self.client.close(); self.engine.dispose()

    def create(self, **changes):
        response = self.client.post("/journal", json={**self.payload, **changes})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_persistent_crud_and_long_short_pnl(self):
        trade = self.create()
        self.assertEqual(trade["net_pnl"], 98)
        self.assertAlmostEqual(trade["r_multiple"], 1.96)
        updated = self.client.put(f"/journal/{trade['id']}", json={**self.payload, "side": "short", "initial_stop": "105"})
        self.assertEqual(updated.json()["net_pnl"], -102)
        self.assertEqual(self.client.get("/journal").json()["total"], 1)
        self.assertEqual(self.client.delete(f"/journal/{trade['id']}").status_code, 200)
        self.assertEqual(self.client.get("/journal").json()["total"], 0)

    def test_performance_curve_counts_realized_trades_and_initial_zero(self):
        self.create(exit_price="90", fees="0")
        self.create(exit_date="2025-01-06", exit_price="120", fees="0")
        self.create(exit_date=None, exit_price=None)
        result = self.client.get("/journal/analytics").json()
        self.assertEqual(result["closed_trades"], 2)
        self.assertEqual(result["open_trades"], 1)
        self.assertEqual(result["win_rate_pct"], 50)
        self.assertEqual(result["profit_factor"], 2)
        self.assertEqual(result["expectancy_per_trade"], 50)
        self.assertEqual(result["max_closed_pnl_drawdown"], 100)
        self.assertEqual(result["pnl_curve"][-1]["cumulative_closed_pnl"], 100)

    def test_invalid_lifecycle_and_precision_rejected_before_write(self):
        for values in [{"exit_price": None}, {"exit_date": "2024-01-01"}, {"initial_stop": "101"},
                       {"quantity": "0"}, {"entry_price": "1.1234567"}, {"entry_date": "2999-01-01"}]:
            with self.subTest(values=values):
                self.assertEqual(self.client.post("/journal", json={**self.payload, **values}).status_code, 422)
        self.assertEqual(self.client.get("/journal").json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
