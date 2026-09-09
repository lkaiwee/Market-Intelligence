import unittest
from datetime import date

from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes.journal import TradeInput, create_trade, delete_trade, update_trade
from app.database import Base
from app.models_journal import TradeJournalEntry
from app.services.trade_journal import journal_analytics, list_trades


class JournalValidationTests(unittest.TestCase):
    def payload(self, **kwargs):
        return dict(ticker="aaa", entry_date="2025-01-01", entry_price="100", quantity="10", **kwargs)

    def test_incomplete_exit_and_reversed_dates_are_rejected(self):
        for kwargs in ({"exit_price": 90}, {"exit_date": "2025-01-02"},
                       {"exit_date": "2024-12-31", "exit_price": 90}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                TradeInput(**self.payload(**kwargs))

    def test_wrong_initial_stop_and_nonfinite_values_are_rejected(self):
        for kwargs in ({"side": "long", "initial_stop": 110}, {"side": "short", "initial_stop": 90}, {"fees": "NaN"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                TradeInput(**self.payload(**kwargs))

    def test_tags_and_ticker_are_normalized(self):
        result = TradeInput(**self.payload(tags=[" Swing ", "swing", "", "Earnings"]))
        self.assertEqual(result.ticker, "AAA")
        self.assertEqual(result.tags, ["swing", "earnings"])


class JournalPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def trade(self, **kwargs):
        values = dict(ticker="AAA", side="long", entry_date=date(2025, 1, 1), entry_price=100,
                      quantity=10, initial_stop=90, fees=5, tags=["trend"])
        values.update(kwargs)
        return TradeInput(**values)

    def test_open_close_edit_delete_and_short_pnl(self):
        opened = create_trade(self.trade(side="short", initial_stop=110), self.db)
        self.assertEqual(opened["status"], "open")
        self.assertIsNone(opened["net_pnl"])
        closed = update_trade(opened["id"], self.trade(side="short", initial_stop=110, exit_date=date(2025, 1, 4), exit_price=90), self.db)
        self.assertEqual(closed["net_pnl"], 95)
        self.assertEqual(closed["r_multiple"], 0.95)
        self.assertEqual(closed["holding_days"], 3)
        self.assertEqual(list_trades(self.db, status="open")["total"], 0)
        self.assertEqual(list_trades(self.db, status="closed")["total"], 1)
        delete_trade(opened["id"], self.db)
        self.assertEqual(self.db.scalars(select(TradeJournalEntry)).all(), [])

    def test_analytics_use_net_pnl_exclude_open_and_start_drawdown_at_zero(self):
        create_trade(self.trade(exit_date=date(2025, 1, 2), exit_price=90, fees=0), self.db)  # -100
        create_trade(self.trade(exit_date=date(2025, 1, 3), exit_price=120, fees=10), self.db)  # +190
        create_trade(self.trade(exit_date=date(2025, 1, 4), exit_price=95, fees=0, initial_stop=None), self.db)  # -50
        create_trade(self.trade(), self.db)  # open, not a realized loss from fees
        result = journal_analytics(self.db)
        self.assertEqual(result["open_trades"], 1)
        self.assertEqual(result["net_pnl"], 40)
        self.assertAlmostEqual(result["expectancy_per_trade"], 40 / 3)
        self.assertAlmostEqual(result["profit_factor"], 190 / 150)
        self.assertAlmostEqual(result["win_rate_pct"], 100 / 3)
        self.assertEqual(result["max_closed_pnl_drawdown"], 100)
        self.assertEqual([p["cumulative_closed_pnl"] for p in result["pnl_curve"]], [-100, 90, 40])
        self.assertEqual(result["trades_with_r_multiple"], 2)
        self.assertAlmostEqual(result["average_r_multiple"], 0.45)

    def test_same_exit_day_is_aggregated_and_no_loss_factor_is_not_infinity(self):
        create_trade(self.trade(exit_date=date(2025, 1, 3), exit_price=120, fees=0), self.db)
        create_trade(self.trade(exit_date=date(2025, 1, 3), exit_price=101, fees=0), self.db)
        result = journal_analytics(self.db)
        self.assertEqual(len(result["pnl_curve"]), 1)
        self.assertEqual(result["pnl_curve"][0]["cumulative_closed_pnl"], 210)
        self.assertIsNone(result["profit_factor"])
        self.assertEqual(result["profit_factor_note"], "No losing closed trades")


if __name__ == "__main__":
    unittest.main()
