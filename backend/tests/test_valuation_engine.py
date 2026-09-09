import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DailyPrice, FundamentalSnapshot, Stock
from app.models_quality import FinancialStatementCache
from app.services.valuation_engine import (
    ValuationInputs, calculate_valuation, equity_dcf, valuation_context,
)


class ValuationTests(unittest.TestCase):
    def setUp(self):
        self.context = {"ticker": "TEST", "current_price": 80,
                        "base_cash_flow": 100, "shares": 10,
                        "implied_trailing_eps": 4, "quote_currency": "USD", "warnings": []}

    def test_constant_cash_flow_matches_perpetuity_hand_calculation(self):
        result = equity_dcf(100, 10, 0, .1, 0, 5)
        # An infinite constant equity distribution of 100 is worth 100 / 10%.
        self.assertAlmostEqual(result["equity_value"], 1000)
        self.assertAlmostEqual(result["fair_value_per_share"], 100)
        self.assertAlmostEqual(result["projections"][0]["present_value"], 100 / 1.1)

    def test_two_stage_projection_and_terminal_value_match_hand_calculation(self):
        result = equity_dcf(100, 20, .1, .12, .03, 2)
        expected = 110 / 1.12 + 121 / 1.12 ** 2 + (121 * 1.03 / .09) / 1.12 ** 2
        self.assertAlmostEqual(result["equity_value"], expected)
        self.assertAlmostEqual(result["fair_value_per_share"], expected / 20)

    def test_equity_model_does_not_subtract_debt_again(self):
        context = {**self.context, "total_debt": 500, "cash": 300}
        result = calculate_valuation(context, ValuationInputs(growth_pct=0, discount_pct=10, terminal_growth_pct=0))
        self.assertAlmostEqual(result["dcf"]["fair_value_per_share"], 100)
        self.assertAlmostEqual(result["dcf"]["buy_below_with_margin_of_safety"], 80)
        self.assertAlmostEqual(result["dcf"]["upside_pct"], 25)
        self.assertAlmostEqual(result["earnings_multiple"]["fair_value"], 84)

    def test_negative_cash_flow_or_earnings_produces_unavailable_model(self):
        result = calculate_valuation({**self.context, "base_cash_flow": -5, "implied_trailing_eps": -2}, ValuationInputs())
        self.assertIsNone(result["dcf"])
        self.assertIsNone(result["earnings_multiple"])
        self.assertIn("negative", result["dcf_unavailable_reason"])
        result = calculate_valuation({**self.context, "base_cash_flow": None, "shares": None, "implied_trailing_eps": None}, ValuationInputs())
        self.assertIsNone(result["dcf"])
        self.assertIsNone(result["earnings_multiple"])

    def test_invalid_growth_spread_and_nonfinite_inputs_are_rejected(self):
        for values in ({"discount_pct": 2, "terminal_growth_pct": 2}, {"growth_pct": -100},
                       {"shares_override": 0}, {"discount_pct": float("nan")},
                       {"base_cash_flow_override": float("inf")}, {"years": 2.5}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                ValuationInputs(**values)

    def test_low_discount_boundary_keeps_bull_scenario_valid(self):
        result = calculate_valuation(self.context, ValuationInputs(discount_pct=1, terminal_growth_pct=-5))
        self.assertEqual(len(result["scenarios"]), 3)
        self.assertGreater(result["scenarios"][2]["discount_pct"], 0)
        self.assertEqual(len(result["sensitivity"]), 25)
        self.assertTrue(any(cell["fair_value"] is None for cell in result["sensitivity"]))

    def test_currency_mismatch_requires_explicit_conversion(self):
        with self.assertRaisesRegex(ValueError, "quote currency"):
            calculate_valuation(self.context, ValuationInputs(base_cash_flow_override=100, cash_flow_currency="EUR"))

    def test_override_is_used_and_missing_current_price_does_not_fabricate_upside(self):
        result = calculate_valuation({**self.context, "current_price": None}, ValuationInputs(
            base_cash_flow_override=200, shares_override=10, growth_pct=0, terminal_growth_pct=0))
        self.assertAlmostEqual(result["dcf"]["fair_value_per_share"], 200)
        self.assertIsNone(result["dcf"]["upside_pct"])

    def test_context_filters_unfinished_closes_and_incompatible_statement_currencies(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(Stock(ticker="TEST"))
            db.flush()
            for day, close in ((date(2026, 9, 8), 100), (date(2026, 9, 9), 999)):
                db.add(DailyPrice(ticker="TEST", trade_date=day, open=close, high=close, low=close, close=close, volume=1))
            db.add(FundamentalSnapshot(ticker="TEST", market_cap=1000, trailing_pe=20))
            db.add(FinancialStatementCache(ticker="TEST", payload={"financial_currency": "EUR", "quote_currency": "USD", "periods": [{"period_end": "2025-12-31", "income_available": True, "cashflow_available": True, "operating_cashflow": 150, "capex": -50}]}))
            db.commit()
            with patch("app.services.valuation_engine.latest_completed_session", return_value=SimpleNamespace(trade_date=date(2026, 9, 8))):
                context = valuation_context(db, "TEST")
            self.assertEqual(context["current_price"], 100)
            self.assertEqual(context["shares"], 10)
            self.assertEqual(context["implied_trailing_eps"], 5)
            self.assertIsNone(context["base_cash_flow"])
            self.assertTrue(any("currencies" in warning for warning in context["warnings"]))


if __name__ == "__main__":
    unittest.main()
