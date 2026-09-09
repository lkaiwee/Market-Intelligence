import asyncio
import unittest
from unittest.mock import patch

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models_quality import FinancialStatementCache
from app.services.earnings_quality import (
    analyze_period, analyze_statements, normalize_statements,
    quality_report, refresh_statement_cache,
)


class EarningsQualityTests(unittest.TestCase):
    def setUp(self):
        self.latest = {"period_end": "2025-12-31", "income_available": True, "cashflow_available": True,
                       "revenue": 1000, "net_income": 100, "operating_cashflow": 130,
                       "capex": -40, "assets": 600, "diluted_shares": 102,
                       "current_assets": 200, "current_liabilities": 100, "debt": 100, "equity": 300,
                       "operating_income": 120, "interest_expense": 10, "stock_compensation": 20}
        self.previous = {"period_end": "2024-12-31", "assets": 400, "revenue": 800, "diluted_shares": 100}

    def test_cash_flow_accruals_and_dilution_use_correct_denominators(self):
        result = analyze_period(self.latest, self.previous)
        self.assertEqual(result["free_cash_flow"], 90)
        self.assertEqual(result["average_assets"], 500)
        self.assertAlmostEqual(result["accruals_to_average_assets"], -.06)
        self.assertAlmostEqual(result["cfo_to_net_income"], 1.3)
        self.assertAlmostEqual(result["cash_conversion_margin"], .13)
        self.assertAlmostEqual(result["fcf_margin"], .09)
        self.assertAlmostEqual(result["revenue_growth_yoy"], .25)
        self.assertAlmostEqual(result["diluted_share_growth_yoy"], .02)

    def test_incompatible_annual_gap_does_not_become_one_year_growth(self):
        result = analyze_period(self.latest, {**self.previous, "period_end": "2023-12-31"})
        self.assertIsNone(result["average_assets"])
        self.assertIsNone(result["accruals_to_average_assets"])
        self.assertIsNone(result["diluted_share_growth_yoy"])

    def test_missing_capex_is_not_zero_and_negative_earnings_ratio_unavailable(self):
        result = analyze_period({**self.latest, "capex": None, "net_income": -10, "equity": -5}, self.previous)
        self.assertIsNone(result["free_cash_flow"])
        self.assertIsNone(result["cfo_to_net_income"])
        self.assertIsNone(result["debt_to_equity"])
        self.assertAlmostEqual(result["accruals_to_average_assets"], -.28)

    def test_zero_debt_is_real_zero_but_zero_denominator_is_unavailable(self):
        result = analyze_period({**self.latest, "debt": 0, "current_liabilities": 0}, self.previous)
        self.assertEqual(result["debt_to_equity"], 0)
        self.assertIsNone(result["current_ratio"])

    def test_statement_dates_are_joined_exactly_without_lookahead_or_filling(self):
        income = pd.DataFrame({pd.Timestamp("2025-12-31"): [1000, 100]}, index=["TotalRevenue", "NetIncome"])
        cash = pd.DataFrame({pd.Timestamp("2025-09-30"): [130, -40]}, index=["OperatingCashFlow", "CapitalExpenditure"])
        balance = pd.DataFrame({pd.Timestamp("2025-12-31"): [600]}, index=["TotalAssets"])
        periods = normalize_statements(income, cash, balance)
        self.assertEqual(len(periods), 2)
        result = analyze_statements({"periods": periods})
        self.assertIsNone(result["latest_period"])
        self.assertEqual(result["checks_available"], 0)
        self.assertIsNone(result["score"])

    def test_score_reports_coverage_and_does_not_penalize_missing_metrics(self):
        report = analyze_statements({"periods": [self.latest, self.previous]})
        self.assertEqual(report["checks_available"], 6)
        sparse = {"period_end": "2025-12-31", "income_available": True, "cashflow_available": True,
                  "net_income": 100, "operating_cashflow": 120}
        report = analyze_statements({"periods": [sparse]})
        self.assertEqual(report["checks_available"], 1)
        self.assertEqual(report["checks_met"], 1)
        self.assertIsNone(report["score"])

    def test_provider_empty_columns_do_not_count_as_available_statements(self):
        empty_values = pd.DataFrame({pd.Timestamp("2025-12-31"): [float("nan")]}, index=["NetIncome"])
        periods = normalize_statements(empty_values, pd.DataFrame(), pd.DataFrame())
        self.assertEqual(periods, [])

    def test_latest_aligned_period_used_when_newer_set_is_incomplete(self):
        newest = {"period_end": "2026-12-31", "income_available": True, "net_income": 500}
        report = analyze_statements({"periods": [newest, self.latest, self.previous]})
        self.assertEqual(report["latest_period"], "2025-12-31")
        self.assertTrue(any("incomplete" in warning for warning in report["warnings"]))

    def test_refresh_persists_real_payload_and_failure_preserves_cache(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            payload = {"periods": [self.latest, self.previous], "financial_currency": "USD"}
            with patch("app.services.earnings_quality._fetch_statements", return_value=payload):
                asyncio.run(refresh_statement_cache(db, "TEST"))
            self.assertEqual(quality_report(db, "TEST")["latest_period"], "2025-12-31")
            with patch("app.services.earnings_quality._fetch_statements", side_effect=RuntimeError("provider down")):
                with self.assertRaises(RuntimeError):
                    asyncio.run(refresh_statement_cache(db, "TEST"))
            self.assertEqual(db.get(FinancialStatementCache, "TEST").payload, payload)


if __name__ == "__main__":
    unittest.main()
