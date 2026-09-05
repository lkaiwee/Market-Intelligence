from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import DashboardOut
from app.services.dashboard import build_dashboard

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
):
    return build_dashboard(db)
