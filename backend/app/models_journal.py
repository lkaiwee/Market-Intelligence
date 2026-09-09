from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TradeJournalEntry(Base):
    __tablename__ = "trade_journal"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 6))
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    fees: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=Decimal("0"))
    initial_stop: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    thesis: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
