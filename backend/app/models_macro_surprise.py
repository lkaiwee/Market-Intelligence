from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MacroRelease(Base):
    __tablename__ = "macro_surprise_releases"
    __table_args__ = (
        UniqueConstraint("indicator", "release_at", "period", "unit", name="uq_macro_surprise_release"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    indicator: Mapped[str] = mapped_column(String(120), index=True)
    release_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period: Mapped[str] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(80))
    actual: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    consensus: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    previous: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    actual_source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consensus_source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
