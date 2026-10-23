from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import api_error
from app.models.pending_operation import PendingOperation
from app.models.user import User
from app.schemas.agent import (
    AgentChatRequest,
    AgentRunDetail,
    AgentRunList,
    ConfirmOperationResponse,
    PendingOperationBrief,
)
from app.services import agent_chat
from app.services import agent_runs as agent_runs_service
from app.services import pending as pending_service

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat")
def agent_chat_route(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    if len(payload.question.strip()) < 2:
        raise api_error(status.HTTP_400_BAD_REQUEST, "question_too_short")
    return StreamingResponse(
        agent_chat.stream_chat(current_user.id, payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs", response_model=AgentRunList)
def list_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentRunList:
    return agent_runs_service.list_runs(db, current_user)


@router.get("/runs/{run_id}", response_model=AgentRunDetail)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentRunDetail:
    return agent_runs_service.get_run(db, current_user, run_id)


@router.post("/operations/{operation_id}/confirm", response_model=ConfirmOperationResponse)
def confirm_operation(
    operation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConfirmOperationResponse:
    operation, action = pending_service.confirm_operation(db, current_user, operation_id)
    return ConfirmOperationResponse(operation=_brief(operation), action=action)


@router.post("/operations/{operation_id}/reject", response_model=PendingOperationBrief)
def reject_operation(
    operation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PendingOperationBrief:
    operation = pending_service.reject_operation(db, current_user, operation_id)
    return _brief(operation)


def _brief(operation: PendingOperation) -> PendingOperationBrief:
    return PendingOperationBrief(
        id=operation.id,
        tool_name=operation.tool_name,
        summary=operation.summary,
        expires_at=operation.expires_at,
    )
