from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_macro_surprise import MacroRelease
from app.services.macro_surprise import macro_surprise_dashboard

router = APIRouter(prefix="/macro-surprise", tags=["Macro Surprise"])


class MacroReleaseInput(BaseModel):
    indicator: str = Field(min_length=1, max_length=120)
    release_at: AwareDatetime
    period: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=80)
    actual: Decimal | None = Field(default=None, max_digits=24, decimal_places=8, allow_inf_nan=False)
    consensus: Decimal | None = Field(default=None, max_digits=24, decimal_places=8, allow_inf_nan=False)
    previous: Decimal | None = Field(default=None, max_digits=24, decimal_places=8, allow_inf_nan=False)
    actual_source: str | None = Field(default=None, max_length=500)
    consensus_source: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("indicator", "period", "unit", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return " ".join(value.split()) if isinstance(value, str) else value

    @field_validator("indicator", "unit")
    @classmethod
    def normalize_series(cls, value: str) -> str:
        return value.casefold()

    @field_validator("actual_source", "consensus_source", "notes", mode="before")
    @classmethod
    def normalize_optional(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("release_at")
    @classmethod
    def normalize_date(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_sources(self):
        if self.actual is not None:
            if self.release_at > datetime.now(timezone.utc):
                raise ValueError("Actual cannot be recorded before the release time.")
            if not self.actual_source:
                raise ValueError("Include the actual release source when recording an actual value.")
        if self.consensus is not None and not self.consensus_source:
            raise ValueError("Include a consensus source when recording a forecast.")
        return self


@router.get("")
def get_releases(db: Session = Depends(get_db)):
    return macro_surprise_dashboard(db)


def save(db: Session, row: MacroRelease, payload: MacroReleaseInput):
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A release with this indicator, release time, period and unit already exists.") from exc
    return macro_surprise_dashboard(db)


@router.post("", status_code=201)
def create_release(payload: MacroReleaseInput, db: Session = Depends(get_db)):
    return save(db, MacroRelease(), payload)


@router.put("/{release_id}")
def update_release(release_id: int, payload: MacroReleaseInput, db: Session = Depends(get_db)):
    row = db.get(MacroRelease, release_id)
    if row is None:
        raise HTTPException(404, "Macro release not found.")
    return save(db, row, payload)


@router.delete("/{release_id}")
def delete_release(release_id: int, db: Session = Depends(get_db)):
    row = db.get(MacroRelease, release_id)
    if row is None:
        raise HTTPException(404, "Macro release not found.")
    db.delete(row)
    db.commit()
    return macro_surprise_dashboard(db)
