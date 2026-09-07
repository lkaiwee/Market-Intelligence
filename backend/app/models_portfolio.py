from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    ticker: Mapped[str] = mapped_column(
        ForeignKey("stocks.ticker", ondelete="CASCADE"),
        primary_key=True,
    )
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    shares: Mapped[Decimal] = mapped_column(Numeric(24, 6))
    opened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
