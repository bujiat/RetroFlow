from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.weekly_reviews import (
    GenerateWeeklyReviewRequest,
    SaveWeeklyReviewRequest,
    WeeklyReviewOut,
)
from app.services import weekly_reviews as weekly_service

router = APIRouter(prefix="/weekly-reviews", tags=["weekly-reviews"])


@router.get("/current", response_model=WeeklyReviewOut)
def get_current_weekly_review(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyReviewOut:
    return weekly_service.get_saved(db, current_user, None)


@router.post("/generate", response_model=WeeklyReviewOut)
def generate_weekly_review(
    payload: GenerateWeeklyReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyReviewOut:
    return weekly_service.generate(
        db,
        current_user,
        payload or GenerateWeeklyReviewRequest(),
    )


@router.get("/{week_start}", response_model=WeeklyReviewOut)
def get_weekly_review(
    week_start: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyReviewOut:
    return weekly_service.get_saved(db, current_user, week_start)


@router.put("/{week_start}", response_model=WeeklyReviewOut)
def save_weekly_review(
    week_start: date,
    payload: SaveWeeklyReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyReviewOut:
    return weekly_service.save(db, current_user, week_start, payload)
