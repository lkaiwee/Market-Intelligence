import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_journal import TradeJournalEntry
from app.services.trade_journal import journal_analytics, list_trades, trade_result

router = APIRouter(prefix="/journal", tags=["Trade Journal"])


class TradeInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    ticker: str = Field(min_length=1, max_length=16)
    side: Literal["long", "short"] = "long"
    entry_date: date
    entry_price: Decimal = Field(gt=0, le=Decimal("1e10"), decimal_places=6)
    quantity: Decimal = Field(gt=0, le=Decimal("1e12"), decimal_places=6)
    exit_date: date | None = None
    exit_price: Decimal | None = Field(default=None, gt=0, le=Decimal("1e10"), decimal_places=6)
    fees: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("1e12"), decimal_places=2)
    initial_stop: Decimal | None = Field(default=None, gt=0, le=Decimal("1e10"), decimal_places=6)
    thesis: str = Field(default="", max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("ticker")
    @classmethod
    def ticker_format(cls, value):
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-^=]{0,15}", value):
            raise ValueError("Use a valid ticker containing letters, digits, dots or hyphens.")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values):
        tags = list(dict.fromkeys(v.strip().lower() for v in values if v.strip()))
        if any(len(tag) > 40 for tag in tags):
            raise ValueError("Each tag must be at most 40 characters.")
        return tags

    @model_validator(mode="after")
    def valid_lifecycle(self):
        today = datetime.now(timezone.utc).date()
        if self.entry_date > today or self.exit_date and self.exit_date > today:
            raise ValueError("Recorded trade dates cannot be later than today's UTC date.")
        if (self.exit_price is None) != (self.exit_date is None):
            raise ValueError("To close a trade, enter both exit date and exit price; leave both empty for an open trade.")
        if self.exit_date is not None and self.exit_date < self.entry_date:
            raise ValueError("Exit date cannot precede entry date.")
        if self.initial_stop is not None:
            if self.side == "long" and self.initial_stop >= self.entry_price or self.side == "short" and self.initial_stop <= self.entry_price:
                raise ValueError("Initial stop must be below entry for a long trade or above entry for a short trade.")
        return self


def _write(trade: TradeJournalEntry, payload: TradeInput):
    for field, value in payload.model_dump(exclude={"tags"}).items():
        setattr(trade, field, value)
    trade.tags_json = json.dumps(payload.tags)
    trade.updated_at = datetime.now(timezone.utc)


@router.get("")
def get_trades(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
               status: Literal["all", "open", "closed"] = "all", db: Session = Depends(get_db)):
    return list_trades(db, limit=limit, offset=offset, status=status)


@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    return journal_analytics(db)


@router.post("")
def create_trade(payload: TradeInput, db: Session = Depends(get_db)):
    trade = TradeJournalEntry()
    _write(trade, payload)
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade_result(trade)


@router.put("/{trade_id}")
def update_trade(trade_id: int, payload: TradeInput, db: Session = Depends(get_db)):
    trade = db.get(TradeJournalEntry, trade_id)
    if trade is None:
        raise HTTPException(404, "Journal trade not found.")
    _write(trade, payload)
    db.commit()
    db.refresh(trade)
    return trade_result(trade)


@router.delete("/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.get(TradeJournalEntry, trade_id)
    if trade is None:
        raise HTTPException(404, "Journal trade not found.")
    db.delete(trade)
    db.commit()
    return {"id": trade_id, "deleted": True}
