from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.actions import (
    ActionEventOut,
    ActionItemOut,
    MyWeekOut,
    PatchActionRequest,
    RejectActionRequest,
    SubmitEvidenceRequest,
)
from app.services import actions as actions_service

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=list[ActionItemOut])
def list_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActionItemOut]:
    return actions_service.list_actions(db, current_user)


@router.get("/my-week", response_model=MyWeekOut)
def my_week(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MyWeekOut:
    return actions_service.get_my_week(db, current_user)


@router.get("/{action_id}/events", response_model=list[ActionEventOut])
def list_action_events(
    action_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActionEventOut]:
    return actions_service.list_events(db, current_user, action_id)


@router.patch("/{action_id}", response_model=ActionItemOut)
def patch_action(
    action_id: UUID,
    payload: PatchActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActionItemOut:
    return actions_service.patch_action(db, current_user, action_id, payload)


@router.post("/{action_id}/evidence", response_model=ActionItemOut)
def submit_evidence(
    action_id: UUID,
    payload: SubmitEvidenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActionItemOut:
    return actions_service.submit_evidence(db, current_user, action_id, payload)


@router.post("/{action_id}/verify", response_model=ActionItemOut)
def verify_action(
    action_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActionItemOut:
    return actions_service.verify_action(db, current_user, action_id)


@router.post("/{action_id}/reject", response_model=ActionItemOut)
def reject_action(
    action_id: UUID,
    payload: RejectActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActionItemOut:
    return actions_service.reject_action(db, current_user, action_id, payload)
