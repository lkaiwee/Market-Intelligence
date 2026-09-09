"""Recorded trades and cash P&L analytics; never changes portfolio holdings."""
from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models_journal import TradeJournalEntry


def trade_result(trade: TradeJournalEntry) -> dict:
    closed = trade.exit_price is not None and trade.exit_date is not None
    direction = Decimal(1) if trade.side == "long" else Decimal(-1)
    gross = (trade.exit_price - trade.entry_price) * trade.quantity * direction if closed else None
    net = gross - trade.fees if gross is not None else None
    distance = (trade.entry_price - trade.initial_stop) * direction if trade.initial_stop is not None else None
    initial_risk = distance * trade.quantity if distance is not None and distance > 0 else None
    return {
        "id": trade.id, "ticker": trade.ticker, "side": trade.side,
        "status": "closed" if closed else "open", "entry_date": trade.entry_date,
        "entry_price": float(trade.entry_price), "quantity": float(trade.quantity),
        "exit_date": trade.exit_date, "exit_price": float(trade.exit_price) if trade.exit_price is not None else None,
        "fees": float(trade.fees), "initial_stop": float(trade.initial_stop) if trade.initial_stop is not None else None,
        "thesis": trade.thesis, "tags": json.loads(trade.tags_json),
        "gross_pnl": float(gross) if gross is not None else None,
        "net_pnl": float(net) if net is not None else None,
        "initial_risk": float(initial_risk) if initial_risk is not None else None,
        "r_multiple": float(net / initial_risk) if net is not None and initial_risk else None,
        "return_on_entry_notional_pct": float(net / (trade.entry_price * trade.quantity) * 100) if net is not None else None,
        "holding_days": (trade.exit_date - trade.entry_date).days if closed else None,
        "created_at": trade.created_at, "updated_at": trade.updated_at,
    }


def list_trades(db: Session, *, limit: int = 100, offset: int = 0, status: str = "all") -> dict:
    query = select(TradeJournalEntry)
    if status == "open":
        query = query.where(TradeJournalEntry.exit_date.is_(None))
    elif status == "closed":
        query = query.where(TradeJournalEntry.exit_date.is_not(None))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(TradeJournalEntry.entry_date.desc(), TradeJournalEntry.id.desc()).offset(offset).limit(limit)).all()
    return {"trades": [trade_result(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def _summary(results: list[dict]) -> dict:
    closed = [r for r in results if r["net_pnl"] is not None]
    wins = [r["net_pnl"] for r in closed if r["net_pnl"] > 0]
    losses = [r["net_pnl"] for r in closed if r["net_pnl"] < 0]
    net = sum(r["net_pnl"] for r in closed)
    gain, loss = sum(wins), -sum(losses)
    multiples = [r["r_multiple"] for r in closed if r["r_multiple"] is not None]
    return {"closed_trades": len(closed), "wins": len(wins), "losses": len(losses),
            "breakeven": len(closed) - len(wins) - len(losses), "net_pnl": net,
            "winning_pnl": gain, "losing_pnl": loss,
            "win_rate_pct": len(wins) / len(closed) * 100 if closed else None,
            "profit_factor": gain / loss if loss > 0 else None,
            "profit_factor_note": "No losing closed trades" if closed and loss == 0 else ("No closed trades" if not closed else None),
            "expectancy_per_trade": net / len(closed) if closed else None,
            "average_win": gain / len(wins) if wins else None,
            "average_loss": loss / len(losses) if losses else None,
            "average_r_multiple": sum(multiples) / len(multiples) if multiples else None,
            "trades_with_r_multiple": len(multiples),
            "closed_trade_fees": sum(r["fees"] for r in closed),
            "average_holding_days": sum(r["holding_days"] for r in closed) / len(closed) if closed else None}


def journal_analytics(db: Session) -> dict:
    results = [trade_result(row) for row in db.scalars(select(TradeJournalEntry)).all()]
    summary = _summary(results)
    by_day: dict = defaultdict(float)
    by_month: dict = defaultdict(list)
    groups: dict = defaultdict(list)
    for result in results:
        if result["net_pnl"] is None:
            continue
        by_day[result["exit_date"]] += result["net_pnl"]
        by_month[result["exit_date"].strftime("%Y-%m")].append(result)
        groups[("side", result["side"])].append(result)
        for tag in result["tags"]:
            groups[("tag", tag)].append(result)
    curve = []
    cumulative, peak, max_drawdown = 0.0, 0.0, 0.0
    for day, pnl in sorted(by_day.items()):
        cumulative += pnl
        peak = max(peak, cumulative)
        drawdown = peak - cumulative
        max_drawdown = max(max_drawdown, drawdown)
        curve.append({"date": day, "daily_closed_pnl": pnl, "cumulative_closed_pnl": cumulative, "drawdown_amount": drawdown})
    return {
        **summary, "open_trades": sum(r["status"] == "open" for r in results),
        "total_trades": len(results), "max_closed_pnl_drawdown": max_drawdown,
        "pnl_curve": curve,
        "monthly": [{"month": month, **_summary(rows)} for month, rows in sorted(by_month.items())],
        "groups": [{"dimension": dimension, "name": name, **_summary(rows)} for (dimension, name), rows in sorted(groups.items())],
        "methodology": "Net P&L = signed entry-to-exit price change × quantity − recorded total fees. R divides net P&L by initial entry-to-stop dollar risk, excluding fees from the risk denominator. Win rate includes breakeven trades in the denominator. The curve aggregates closed P&L by exit date, begins at zero and is not account NAV or total investment return. Drawdown measures dollars below that curve's previous peak, including the initial zero. Open trades are excluded from realized statistics. Partial exits should be recorded as separate lots with allocated fees; journal entries do not update portfolio holdings.",
    }
