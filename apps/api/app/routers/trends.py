from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.trends import TrendsSummary
from app.services import trends as trends_service

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("/summary", response_model=TrendsSummary)
def trends_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrendsSummary:
    return trends_service.get_summary(db, current_user)
