import unittest
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
from pydantic import ValidationError

from app.services.backtesting import BacktestRequest, simulate
from app.services.setup_scanner import indicators, price_frame, scan_ticker


def rows(count=260):
    return [SimpleNamespace(trade_date=date(2025, 1, 1) + timedelta(days=i), open=100+i*.1,
                            high=101+i*.1, low=99+i*.1, close=100+i*.1, volume=1000)
            for i in range(count)]


class ScannerTests(unittest.TestCase):
    def test_negative_volume_is_excluded_before_scanning(self):
        sample = rows(80)
        sample[-1].volume = -1000
        self.assertEqual(len(price_frame(sample)), 79)
        self.assertEqual(scan_ticker("TEST", sample, sample[-1].trade_date)["status"], "STALE")

    def test_breakout_uses_prior_high_and_prior_volume_baseline(self):
        sample = rows()
        sample[-1].close = sample[-1].high = 150
        sample[-1].volume = 1600
        result = scan_ticker("TEST", sample, sample[-1].trade_date)
        self.assertTrue(next(x for x in result["setups"] if x["id"] == "BREAKOUT")["matched"])
        self.assertEqual(result["volume_ratio"], 1.6)
        self.assertLess(result["stop_reference"], result["price"])
        self.assertAlmostEqual(result["target_2r"] - result["price"],
                               2 * (result["price"] - result["stop_reference"]), places=3)

    def test_future_bar_cannot_create_signal(self):
        sample = rows()
        target = sample[-2].trade_date
        before = scan_ticker("TEST", sample[:-1], target)
        sample[-1].close = sample[-1].high = 1000
        after = scan_ticker("TEST", sample, target)
        self.assertEqual(before, after)

    def test_stale_or_short_series_are_explicit(self):
        sample = rows()
        self.assertEqual(scan_ticker("TEST", sample, sample[-1].trade_date + timedelta(days=1))["status"], "STALE")
        self.assertEqual(scan_ticker("TEST", sample[:10], sample[9].trade_date)["status"], "INSUFFICIENT_DATA")

    def test_flat_series_has_neutral_rsi_and_no_nonfinite_values(self):
        sample = rows(80)
        for row in sample:
            row.open = row.close = 100
            row.high, row.low = 101, 99
        self.assertEqual(indicators(price_frame(sample)).iloc[-1]["rsi"], 50)


class BacktestTests(unittest.TestCase):
    def request(self, **changes):
        defaults = dict(ticker="TEST", fast_period=2, slow_period=3, stop_atr=None,
                        commission_bps=0, slippage_bps=0, allocation_pct=100)
        defaults.update(changes)
        return BacktestRequest(**defaults)

    def test_next_open_execution_never_uses_signal_close(self):
        sample = rows(15)
        sample[3].open = sample[3].high = 110
        result = simulate(price_frame(sample), self.request())
        self.assertEqual(result["open_position"]["entry_price"], 110)
        self.assertEqual(result["open_position"]["entry_date"], sample[3].trade_date)
        self.assertEqual(result["open_position"]["shares"], 90)

    def test_costs_reduce_equity_and_affordable_shares_never_overdraw(self):
        sample = price_frame(rows(80))
        free = simulate(sample, self.request())
        costly = simulate(sample, self.request(commission_bps=100, slippage_bps=100))
        self.assertLess(costly["metrics"]["final_equity"], free["metrics"]["final_equity"])
        self.assertGreater(costly["metrics"]["fees_paid"], 0)
        self.assertGreaterEqual(min(x["equity"] for x in costly["equity_curve"]), 0)

    def test_future_prices_do_not_change_existing_equity_curve(self):
        sample = rows(80)
        first = simulate(price_frame(sample[:50]), self.request())
        for row in sample[50:]:
            row.open *= 3; row.high *= 3; row.low *= 3; row.close *= 3
        full = simulate(price_frame(sample), self.request())
        self.assertEqual(first["equity_curve"], full["equity_curve"][:len(first["equity_curve"])])

    def test_stop_has_adverse_priority_and_gaps_fill_at_open(self):
        sample = rows(45)
        sample[20].low = 50
        sample[20].high = 200
        request = self.request(stop_atr=2, target_r=2, start_date=sample[20].trade_date)
        result = simulate(price_frame(sample), request)
        self.assertEqual(result["trades"][0]["exit_reason"], "ATR_STOP")
        self.assertLess(result["trades"][0]["pnl"], 0)
        sample = rows(45)
        sample[21].open, sample[21].low, sample[21].close, sample[21].high = 80, 79, 81, 82
        result = simulate(price_frame(sample), self.request(stop_atr=2, start_date=sample[20].trade_date))
        self.assertEqual(result["trades"][0]["exit_price"], 80)

    def test_closed_trade_statistics_exclude_open_position(self):
        result = simulate(price_frame(rows(50)), self.request())
        self.assertIsNotNone(result["open_position"])
        self.assertEqual(result["metrics"]["closed_trades"], 0)
        self.assertIsNone(result["metrics"]["win_rate_pct"])
        self.assertIsNone(result["metrics"]["profit_factor"])

    def test_existing_target_gap_fills_before_later_intraday_stop(self):
        sample = rows(45)
        sample[21].open, sample[21].high, sample[21].low, sample[21].close = 120, 121, 50, 110
        result = simulate(price_frame(sample), self.request(stop_atr=2, target_r=2, start_date=sample[20].trade_date))
        trade = result["trades"][0]
        self.assertEqual(trade["exit_reason"], "R_TARGET")
        self.assertEqual(trade["exit_date"], sample[21].trade_date)
        self.assertEqual(trade["exit_price"], 120)
        self.assertGreater(trade["pnl"], 0)

    def test_end_date_and_warmup_are_honored(self):
        sample = rows(50)
        result = simulate(price_frame(sample), self.request(end_date=sample[25].trade_date))
        self.assertEqual(result["actual_end"], sample[25].trade_date)
        self.assertEqual(result["warmup_bars"], 3)
        with self.assertRaises(ValueError):
            simulate(price_frame(sample[:4]), self.request())

    def test_bad_parameters_fail_validation(self):
        for changes in [{"initial_capital": 0}, {"allocation_pct": 101}, {"slippage_bps": -1},
                        {"commission_bps": np.nan}, {"slow_period": 2}, {"target_r": 2},
                        {"rsi_entry": 50, "rsi_exit": 50}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.request(**changes)


if __name__ == "__main__":
    unittest.main()
