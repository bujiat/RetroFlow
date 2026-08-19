from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.retros import CreateRetroRequest, PublishRetroRequest, RetroDetail, RetroListItem
from app.services import retros as retros_service

router = APIRouter(prefix="/retros", tags=["retros"])


@router.get("", response_model=list[RetroListItem])
def list_retros(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RetroListItem]:
    return retros_service.list_retros(db, current_user)


@router.post("", response_model=RetroListItem, status_code=status.HTTP_201_CREATED)
def create_retro(
    payload: CreateRetroRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetroListItem:
    return retros_service.create_retro(db, current_user, payload)


@router.post("/{retro_id}/analyze", response_model=RetroDetail)
def analyze_retro(
    retro_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetroDetail:
    return retros_service.analyze_retro(db, current_user, retro_id)


@router.post("/{retro_id}/publish", response_model=RetroDetail)
def publish_retro(
    retro_id: UUID,
    payload: PublishRetroRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetroDetail:
    return retros_service.publish_retro(db, current_user, retro_id, payload)


@router.get("/{retro_id}", response_model=RetroDetail)
def get_retro(
    retro_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetroDetail:
    return retros_service.get_retro(db, current_user, retro_id)
