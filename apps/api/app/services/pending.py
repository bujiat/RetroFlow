from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent.loop import AgentStep
from app.core.errors import api_error
from app.models.pending_operation import PendingOperation
from app.models.user import User
from app.schemas.actions import ActionItemOut
from app.schemas.agent import PendingOperationBrief
from app.services import actions as actions_service


def confirm_operation(db: Session, user: User, operation_id: UUID) -> tuple[PendingOperation, ActionItemOut]:
    operation = _pending_for_user(db, user, operation_id)
    operation.status = "approved"
    operation.resolved_at = datetime.now(UTC)
    try:
        action = _apply(db, user, operation)
    except HTTPException:
        operation.status = "pending"
        operation.resolved_at = None
        raise
    return operation, action


def reject_operation(db: Session, user: User, operation_id: UUID) -> PendingOperation:
    operation = _pending_for_user(db, user, operation_id)
    operation.status = "rejected"
    operation.resolved_at = datetime.now(UTC)
    db.commit()
    return operation


def pending_from_steps(steps: list[AgentStep]) -> list[PendingOperationBrief]:
    briefs: list[PendingOperationBrief] = []
    for step in steps:
        if step.name not in {"propose_action", "propose_status_change"}:
            continue
        data = step.result.get("data")
        if not isinstance(data, dict) or data.get("created") is not True:
            continue
        briefs.append(
            PendingOperationBrief(
                id=UUID(str(data["id"])),
                tool_name=str(data["tool_name"]),
                summary=str(data["summary"]),
                expires_at=datetime.fromisoformat(str(data["expires_at"])),
            )
        )
    return briefs


def _apply(db: Session, user: User, operation: PendingOperation) -> ActionItemOut:
    arguments = operation.arguments
    if operation.tool_name == "propose_action":
        return actions_service.create_action_for_problem(
            db,
            user,
            problem_id=UUID(str(arguments["problem_id"])),
            title=str(arguments["title"]),
            description=str(arguments["description"]),
            owner=str(arguments["owner"]),
            due_date=datetime.strptime(str(arguments["due_date"]), "%Y-%m-%d").date(),
            success_criteria=str(arguments["success_criteria"]),
        )
    if operation.tool_name == "propose_status_change":
        return actions_service.apply_proposed_status_change(db, user, arguments)
    raise api_error(status.HTTP_409_CONFLICT, "unknown_operation")


def _pending_for_user(db: Session, user: User, operation_id: UUID) -> PendingOperation:
    operation = db.get(PendingOperation, operation_id)
    if operation is None or operation.user_id != user.id:
        raise api_error(status.HTTP_404_NOT_FOUND, "operation_not_found")
    if operation.status != "pending":
        raise api_error(status.HTTP_409_CONFLICT, "operation_already_resolved")
    if operation.expires_at <= datetime.now(UTC):
        operation.status = "expired"
        operation.resolved_at = datetime.now(UTC)
        db.commit()
        raise api_error(status.HTTP_409_CONFLICT, "operation_expired")
    return operation
