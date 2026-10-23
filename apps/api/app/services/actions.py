from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models.action_item import ActionItem
from app.models.user import User
from app.repositories import actions as actions_repo
from app.repositories import analysis as analysis_repo
from app.schemas.actions import (
    ActionEventOut,
    ActionItemOut,
    MyWeekOut,
    PatchActionRequest,
    RejectActionRequest,
    SubmitEvidenceRequest,
)

# PATCH 只允许这些跳转；证据/验收走专用接口，避免用通用 PATCH 绕过规则
_PATCH_TRANSITIONS = {
    ("open", "in_progress"),
    ("in_progress", "open"),
    ("open", "cancelled"),
    ("in_progress", "cancelled"),
}

_ACTIVE = frozenset({"open", "in_progress"})


def proposed_change_is_allowed(current_status: str, change: str) -> bool:
    if change == "start":
        return (current_status, "in_progress") in _PATCH_TRANSITIONS
    if change == "reopen":
        return (current_status, "open") in _PATCH_TRANSITIONS
    if change == "cancel":
        return (current_status, "cancelled") in _PATCH_TRANSITIONS
    if change in {"verify", "reject"}:
        return current_status == "evidence_submitted"
    return False


def list_actions(db: Session, user: User) -> list[ActionItemOut]:
    rows = actions_repo.list_action_items_for_user(db, user.id)
    return [ActionItemOut.model_validate(row) for row in rows]


def get_my_week(db: Session, user: User) -> MyWeekOut:
    """Three buckets only — keep the week view cognitively light."""
    today = datetime.now(UTC).date()
    week_end = today + timedelta(days=(6 - today.weekday()))  # Sunday of this week

    overdue: list[ActionItemOut] = []
    due_this_week: list[ActionItemOut] = []
    awaiting_verify: list[ActionItemOut] = []

    for row in actions_repo.list_action_items_for_user(db, user.id):
        if row.status == "evidence_submitted":
            awaiting_verify.append(ActionItemOut.model_validate(row))
            continue
        if row.status not in _ACTIVE:
            continue
        if row.due_date < today:
            overdue.append(ActionItemOut.model_validate(row))
        elif row.due_date <= week_end:
            due_this_week.append(ActionItemOut.model_validate(row))

    return MyWeekOut(
        overdue=overdue,
        due_this_week=due_this_week,
        awaiting_verify=awaiting_verify,
    )


def list_events(db: Session, user: User, action_id: UUID) -> list[ActionEventOut]:
    item = actions_repo.get_action_for_user(db, user_id=user.id, action_id=action_id)
    if item is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "action_not_found")
    rows = actions_repo.list_events_for_action(
        db,
        user_id=user.id,
        action_id=action_id,
    )
    return [ActionEventOut.model_validate(row) for row in rows]


def patch_action(
    db: Session,
    user: User,
    action_id: UUID,
    payload: PatchActionRequest,
) -> ActionItemOut:
    item = _get(db, user, action_id)
    target = payload.status
    if (item.status, target) not in _PATCH_TRANSITIONS:
        raise api_error(status.HTTP_409_CONFLICT, "invalid_status_transition")

    previous = item.status
    item.status = target
    event_type = "cancelled" if target == "cancelled" else "status_changed"
    actions_repo.add_event(
        db,
        user_id=user.id,
        action_id=item.id,
        event_type=event_type,
        from_status=previous,
        to_status=target,
    )
    db.commit()
    db.refresh(item)
    return ActionItemOut.model_validate(item)


def submit_evidence(
    db: Session,
    user: User,
    action_id: UUID,
    payload: SubmitEvidenceRequest,
) -> ActionItemOut:
    item = _get(db, user, action_id)
    if item.status not in {"open", "in_progress"}:
        raise api_error(status.HTTP_409_CONFLICT, "invalid_status_transition")

    previous = item.status
    item.status = "evidence_submitted"
    actions_repo.add_event(
        db,
        user_id=user.id,
        action_id=item.id,
        event_type="evidence_submitted",
        from_status=previous,
        to_status="evidence_submitted",
        note=payload.completion_note,
        evidence_text=payload.evidence_text,
        evidence_url=payload.evidence_url,
    )
    db.commit()
    db.refresh(item)
    return ActionItemOut.model_validate(item)


def verify_action(db: Session, user: User, action_id: UUID) -> ActionItemOut:
    item = _get(db, user, action_id)
    if item.status != "evidence_submitted":
        raise api_error(status.HTTP_409_CONFLICT, "invalid_status_transition")

    previous = item.status
    item.status = "verified"
    item.verified_at = datetime.now(UTC)
    actions_repo.add_event(
        db,
        user_id=user.id,
        action_id=item.id,
        event_type="verified",
        from_status=previous,
        to_status="verified",
    )
    db.commit()
    db.refresh(item)
    return ActionItemOut.model_validate(item)


def reject_action(
    db: Session,
    user: User,
    action_id: UUID,
    payload: RejectActionRequest,
) -> ActionItemOut:
    item = _get(db, user, action_id)
    if item.status != "evidence_submitted":
        raise api_error(status.HTTP_409_CONFLICT, "invalid_status_transition")

    previous = item.status
    item.status = "in_progress"
    actions_repo.add_event(
        db,
        user_id=user.id,
        action_id=item.id,
        event_type="rejected",
        from_status=previous,
        to_status="in_progress",
        note=payload.reject_reason,
    )
    db.commit()
    db.refresh(item)
    return ActionItemOut.model_validate(item)


def _get(db: Session, user: User, action_id: UUID):
    item = actions_repo.get_action_for_user(db, user_id=user.id, action_id=action_id)
    if item is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "action_not_found")
    return item


def create_action_for_problem(
    db: Session,
    user: User,
    *,
    problem_id: UUID,
    title: str,
    description: str,
    owner: str,
    due_date: date,
    success_criteria: str,
) -> ActionItemOut:
    problem = analysis_repo.get_problem_for_user(db, user_id=user.id, problem_id=problem_id)
    if problem is None or problem.disposition != "kept":
        raise api_error(status.HTTP_404_NOT_FOUND, "problem_not_found")
    item = ActionItem(
        id=uuid4(),
        user_id=user.id,
        retro_id=problem.retro_id,
        problem_occurrence_id=problem.id,
        title=title,
        description=description,
        owner=owner,
        due_date=due_date,
        success_criteria=success_criteria,
        status="open",
    )
    db.add(item)
    db.flush()
    actions_repo.add_event(
        db,
        user_id=user.id,
        action_id=item.id,
        event_type="created",
        from_status=None,
        to_status="open",
    )
    db.commit()
    db.refresh(item)
    return ActionItemOut.model_validate(item)


def apply_proposed_status_change(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> ActionItemOut:
    action_id = UUID(str(arguments["action_id"]))
    change = str(arguments["change"])
    if change == "verify":
        return verify_action(db, user, action_id)
    if change == "reject":
        return reject_action(
            db,
            user,
            action_id,
            RejectActionRequest(reject_reason=str(arguments.get("reason") or "")),
        )
    target = {"start": "in_progress", "reopen": "open", "cancel": "cancelled"}[change]
    return patch_action(db, user, action_id, PatchActionRequest(status=target))
