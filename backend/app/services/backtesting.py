from __future__ import annotations

from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from app.core.market_sessions import latest_completed_session
from app.models import DailyPrice
from app.services.setup_scanner import indicators, price_frame


class BacktestRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    ticker: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9.^-]+$")
    strategy: Literal["sma_trend", "breakout", "rsi_reversion"] = "sma_trend"
    start_date: date | None = None
    end_date: date | None = None
    initial_capital: float = Field(default=10000, gt=0, le=1e10)
    allocation_pct: float = Field(default=95, gt=0, le=100)
    commission_bps: float = Field(default=10, ge=0, le=500)
    slippage_bps: float = Field(default=5, ge=0, le=500)
    fast_period: int = Field(default=20, ge=2, le=150)
    slow_period: int = Field(default=50, ge=3, le=250)
    breakout_period: int = Field(default=20, ge=5, le=100)
    exit_period: int = Field(default=10, ge=2, le=100)
    rsi_entry: float = Field(default=30, ge=5, le=50)
    rsi_exit: float = Field(default=55, ge=50, le=95)
    stop_atr: float | None = Field(default=2, gt=0, le=10)
    target_r: float | None = Field(default=None, gt=0, le=20)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value):
        return value.upper()

    @model_validator(mode="after")
    def validate_model(self):
        if self.fast_period >= self.slow_period:
            raise ValueError("Fast SMA period must be below slow SMA period.")
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date.")
        if self.rsi_entry >= self.rsi_exit:
            raise ValueError("RSI entry threshold must be below the exit threshold.")
        if self.target_r is not None and self.stop_atr is None:
            raise ValueError("A target in R requires an ATR stop.")
        return self


def _safe(value, decimals=4):
    return round(float(value), decimals) if value is not None and np.isfinite(value) else None


def simulate(frame: pd.DataFrame, request: BacktestRequest) -> dict:
    """Daily long-only simulation. Signals at t close execute at t+1 open."""
    data = indicators(frame)
    if request.end_date:
        data = data.loc[data.index <= request.end_date]
    if request.strategy == "sma_trend":
        fast = data["close"].rolling(request.fast_period).mean()
        slow = data["close"].rolling(request.slow_period).mean()
        entries, exits = fast > slow, fast <= slow
        warmup = request.slow_period
    elif request.strategy == "breakout":
        entries = data["close"] > data["high"].shift(1).rolling(request.breakout_period).max()
        exits = data["close"] < data["low"].shift(1).rolling(request.exit_period).min()
        warmup = max(request.breakout_period, request.exit_period) + 1
    else:
        entries, exits = data["rsi"] < request.rsi_entry, data["rsi"] > request.rsi_exit
        warmup = 15
    if request.stop_atr is not None:
        warmup = max(warmup, 15)
    eligible = [i for i, day in enumerate(data.index)
                if i >= warmup and (request.start_date is None or day >= request.start_date)]
    if len(eligible) < 3:
        raise ValueError("At least three simulation sessions after indicator warm-up are required. Refresh prices or widen the date range.")
    start = eligible[0]
    cash, shares = request.initial_capital, 0
    position = None
    trades, curve = [], []
    fees = request.commission_bps / 10000
    slip = request.slippage_bps / 10000
    total_fees, exposed = 0., 0
    benchmark_entry = float(data.iloc[start]["open"]) * (1 + slip)
    benchmark_shares = request.initial_capital / (benchmark_entry * (1 + fees))
    peak = request.initial_capital

    def close_position(day, raw_price, reason):
        nonlocal cash, shares, position, total_fees
        execution = float(raw_price) * (1 - slip)
        fee = shares * execution * fees
        proceeds = shares * execution - fee
        pnl = proceeds - position["cost"]
        cash += proceeds
        total_fees += fee
        trades.append({"entry_date": position["entry_date"], "exit_date": day,
                       "signal_date": position["signal_date"], "entry_price": _safe(position["entry"]),
                       "exit_price": _safe(execution), "shares": shares, "pnl": _safe(pnl),
                       "return_pct": _safe(pnl / position["cost"] * 100), "exit_reason": reason,
                       "fees": _safe(position["entry_fee"] + fee)})
        shares, position = 0, None

    for i in range(start, len(data)):
        day, row = data.index[i], data.iloc[i]
        previous = data.iloc[i - 1]
        was_exposed = shares > 0
        held_at_open = shares > 0
        if shares and bool(exits.iloc[i - 1]):
            close_position(day, row["open"], "SIGNAL_NEXT_OPEN")
        elif not shares and bool(entries.iloc[i - 1]):
            execution = float(row["open"]) * (1 + slip)
            budget = cash * request.allocation_pct / 100
            shares = int(budget // (execution * (1 + fees)))
            if shares:
                fee = shares * execution * fees
                cost = shares * execution + fee
                cash -= cost
                total_fees += fee
                stop = max(.01, execution - float(previous["atr"]) * request.stop_atr) if request.stop_atr else None
                target = execution + request.target_r * (execution - stop) if request.target_r else None
                position = {"entry_date": day, "signal_date": data.index[i - 1], "entry": execution,
                            "cost": cost, "entry_fee": fee, "stop": stop, "target": target}
                was_exposed = True
        if shares:
            # Existing orders can fill at the opening print before any later
            # intraday high/low. Only genuinely unordered touches are stop-first.
            if held_at_open and position["stop"] is not None and row["open"] <= position["stop"]:
                close_position(day, row["open"], "ATR_STOP")
            elif held_at_open and position["target"] is not None and row["open"] >= position["target"]:
                close_position(day, row["open"], "R_TARGET")
            elif position["stop"] is not None and row["low"] <= position["stop"]:
                close_position(day, min(float(row["open"]), position["stop"]), "ATR_STOP")
            elif position["target"] is not None and row["high"] >= position["target"]:
                close_position(day, max(float(row["open"]), position["target"]), "R_TARGET")
        exposed += int(was_exposed or shares > 0)
        equity = cash + shares * float(row["close"])
        peak = max(peak, equity)
        curve.append({"date": day, "equity": _safe(equity),
                      "benchmark": _safe(benchmark_shares * float(row["close"])),
                      "drawdown_pct": _safe((equity / peak - 1) * 100)})

    values = pd.Series([request.initial_capital] + [point["equity"] for point in curve])
    returns = values.pct_change().dropna()
    volatility = float(returns.std(ddof=1))
    wins = [trade["pnl"] for trade in trades if trade["pnl"] > 0]
    losses = [trade["pnl"] for trade in trades if trade["pnl"] < 0]
    final = float(values.iloc[-1])
    days = max(1, (curve[-1]["date"] - curve[0]["date"]).days + 1)
    annualized_log = np.log(final / request.initial_capital) * (365.25 / days) if final > 0 else None
    annualized = np.expm1(annualized_log) if annualized_log is not None and annualized_log < 700 else None
    open_position = None
    if position:
        open_position = {"entry_date": position["entry_date"], "entry_price": _safe(position["entry"]),
                         "shares": shares, "market_value": _safe(shares * float(data.iloc[-1]["close"])),
                         "unrealized_pnl": _safe(shares * float(data.iloc[-1]["close"]) - position["cost"]),
                         "stop": _safe(position["stop"]), "target": _safe(position["target"])}
    return {"ticker": request.ticker, "strategy": request.strategy, "requested_start": request.start_date,
            "requested_end": request.end_date, "actual_start": curve[0]["date"], "actual_end": curve[-1]["date"],
            "sessions": len(curve), "warmup_bars": start, "parameters": request.model_dump(),
            "metrics": {"initial_capital": request.initial_capital, "final_equity": _safe(final),
                        "total_return_pct": _safe((final / request.initial_capital - 1) * 100),
                        "annualized_return_pct": _safe(annualized * 100) if annualized is not None else None,
                        "benchmark_return_pct": _safe((curve[-1]["benchmark"] / request.initial_capital - 1) * 100),
                        "max_drawdown_pct": min(point["drawdown_pct"] for point in curve),
                        "annualized_volatility_pct": _safe(volatility * np.sqrt(252) * 100),
                        "sharpe_zero_rate": _safe(returns.mean() / volatility * np.sqrt(252)) if volatility > 0 else None,
                        "closed_trades": len(trades), "win_rate_pct": _safe(len(wins) / len(trades) * 100) if trades else None,
                        "profit_factor": _safe(sum(wins) / abs(sum(losses))) if losses else None,
                        "expectancy": _safe(sum(t["pnl"] for t in trades) / len(trades)) if trades else None,
                        "fees_paid": _safe(total_fees), "exposure_pct": _safe(exposed / len(curve) * 100)},
            "equity_curve": curve, "trades": trades, "open_position": open_position,
            "notes": ["Long-only, whole shares, no leverage. Signals use a completed close and execute at the next available open.",
                      "Commission and adverse slippage apply on each fill. Existing stops and targets crossed at the open fill there first; otherwise stop wins if both levels are touched in the same daily bar.",
                      "Open positions remain marked to the final close; closed-trade statistics exclude them. Profit factor is unavailable without a losing trade.",
                      "Uses stored Yahoo daily price history. Dividends, taxes, market impact and delisted stocks are not modeled; this is not total-return or point-in-time fundamental backtesting.",
                      "Benchmark buys fractional shares at the first simulated open with the same entry costs and holds to the final close. Cash earns zero.",
                      "Annualized statistics from short samples are unstable. Parameter selection on this same history can overfit."]}


def run_backtest(db, request: BacktestRequest):
    completed = latest_completed_session().trade_date
    end = min(request.end_date, completed) if request.end_date else completed
    rows = db.scalars(select(DailyPrice).where(DailyPrice.ticker == request.ticker,
                                             DailyPrice.trade_date <= end)
                      .order_by(DailyPrice.trade_date.desc()).limit(3000)).all()
    frame = price_frame(rows)
    if frame.empty:
        raise ValueError(f"No stored completed price history for {request.ticker}. Refresh the stock first.")
    result = simulate(frame, request)
    result["data_latest_date"] = frame.index[-1]
    result["latest_completed_session"] = completed
    if end > frame.index[-1]:
        result["notes"].append(f"Stored data ends on {frame.index[-1]}, before the requested end {end}.")
    return result
