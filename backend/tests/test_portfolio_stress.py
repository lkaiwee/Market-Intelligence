import unittest
from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DailyPrice, Stock
from app.models_portfolio import PortfolioPosition
from app.services.portfolio_stress import analyze_stress, historical_risk, pair_statistics, return_frame


class ReturnAlignmentTests(unittest.TestCase):
    def test_missing_close_is_not_filled_or_treated_as_one_day_return(self):
        days = [date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 4)]
        result = return_frame({"AAA": {days[0]: 100, days[2]: 110, days[3]: 121, days[4]: 121},
                               "BBB": dict(zip(days, [100, 101, 102, 103, 104]))}, days[-1], 60)
        self.assertTrue(pd.isna(result.loc["2026-09-01", "AAA"]))
        self.assertTrue(pd.isna(result.loc["2026-09-02", "AAA"]))
        self.assertAlmostEqual(result.loc["2026-09-03", "AAA"], 0.1)

    def test_holiday_is_not_an_artificial_missing_return(self):
        result = return_frame({"AAA": {date(2026, 9, 4): 100, date(2026, 9, 8): 110}}, date(2026, 9, 8), 60)
        self.assertNotIn(pd.Timestamp("2026-09-07"), result.index)
        self.assertAlmostEqual(result.loc["2026-09-08", "AAA"], 0.1)

    def test_pair_statistics_require_samples_and_handle_constant_series(self):
        x = pd.Series([i / 10000 for i in range(100)])
        frame = pd.DataFrame({"A": 2 * x, "SPY": x, "CONST": 1.0})
        result = pair_statistics(frame, "A", "SPY")
        self.assertAlmostEqual(result["beta"], 2)
        self.assertAlmostEqual(result["correlation"], 1)
        self.assertIsNone(pair_statistics(frame.iloc[:59], "A", "SPY")["beta"])
        self.assertIsNone(pair_statistics(frame, "CONST", "SPY")["correlation"])

    def test_historical_var_expected_shortfall_and_minimum_sample(self):
        returns = pd.Series([-0.10] * 10 + [0.01] * 90, index=pd.bdate_range("2025-01-01", periods=100))
        result = historical_risk(returns, 10000, 0.95)
        self.assertAlmostEqual(result["one_day_var_amount"], 1000)
        self.assertAlmostEqual(result["one_day_expected_shortfall_amount"], 1000)
        self.assertEqual(result["tail_observations"], 10)
        self.assertIsNone(historical_risk(returns.iloc[:59], 10000, 0.95))


class PortfolioStressTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([Stock(ticker="AAA"), Stock(ticker="BBB"), Stock(ticker="SPY")])
        self.db.flush()
        self.db.add_all([PortfolioPosition(ticker="AAA", shares=Decimal(10), entry_price=Decimal(100)),
                         PortfolioPosition(ticker="BBB", shares=Decimal(5), entry_price=Decimal(50))])
        self.db.add(DailyPrice(ticker="AAA", trade_date=date(2026, 9, 4), open=100, high=100, low=100, close=100, volume=100))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_uniform_shock_exposes_partial_coverage(self):
        result = analyze_stress(self.db, market_shock_pct=-20, as_of=date(2026, 9, 4))
        self.assertEqual(result["scenario"]["covered_pnl"], -200)
        self.assertIsNone(result["scenario"]["total_pnl"])
        self.assertEqual(result["scenario"]["missing_tickers"], ["BBB"])
        self.assertIsNone(result["metrics"])

    def test_missing_beta_is_not_silently_assumed_to_be_one(self):
        result = analyze_stress(self.db, mode="beta", as_of=date(2026, 9, 4))
        self.assertIsNone(result["scenario"]["holdings"][0]["applied_shock_pct"])
        result = analyze_stress(self.db, mode="beta", shocks={"AAA": -5}, as_of=date(2026, 9, 4))
        self.assertEqual(result["scenario"]["holdings"][0]["pnl"], -50)


if __name__ == "__main__":
    unittest.main()
