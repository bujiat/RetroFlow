from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.agent.context import current_run_id
from app.agent.tools.base import ToolSpec
from app.models.pending_operation import PendingOperation
from app.repositories import actions as actions_repo
from app.repositories import analysis as analysis_repo
from app.services.actions import proposed_change_is_allowed

PENDING_TTL = timedelta(hours=24)
StatusChange = Literal["start", "reopen", "cancel", "verify", "reject"]


class ProposeActionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: UUID = Field(description="要挂上行动项的问题 id，形如 problem:<uuid>。")
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=2000)
    owner: str = Field(min_length=1, max_length=320)
    due_date: str = Field(description="截止日期，YYYY-MM-DD。")
    success_criteria: str = Field(min_length=1, max_length=2000)
    basis: str = Field(min_length=1, max_length=500, description="为什么建议创建这条行动项。")

    @field_validator("problem_id", mode="before")
    @classmethod
    def strip_problem_prefix(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("problem:"):
            return value.removeprefix("problem:")
        return value

    @field_validator("title", "description", "owner", "success_criteria", "basis")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("due_date")
    @classmethod
    def iso_date(cls, value: str) -> str:
        datetime.strptime(value, "%Y-%m-%d")
        return value


class ProposeStatusChangeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: UUID = Field(description="行动项 id，形如 action:<uuid>。")
    change: StatusChange = Field(
        description="start 开始；reopen 重新打开；cancel 取消；verify 验收通过；reject 驳回证据。",
    )
    basis: str = Field(min_length=1, max_length=500, description="给用户看的理由。")
    reason: str | None = Field(default=None, max_length=2000, description="驳回时必填。")

    @field_validator("action_id", mode="before")
    @classmethod
    def strip_action_prefix(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("action:"):
            return value.removeprefix("action:")
        return value

    @field_validator("basis")
    @classmethod
    def strip_basis(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def reject_needs_reason(self) -> "ProposeStatusChangeArgs":
        if self.change == "reject" and not self.reason:
            raise ValueError("驳回必须填写 reason")
        return self


def execute_propose_action(
    db: Session,
    user_id: UUID,
    args: ProposeActionArgs,
) -> dict[str, object]:
    problem = analysis_repo.get_problem_for_user(db, user_id=user_id, problem_id=args.problem_id)
    if problem is None or problem.disposition != "kept":
        return {"created": False, "error": "problem_not_found"}
    summary = f"创建行动项：{args.title}"
    operation = _insert(
        db,
        user_id=user_id,
        tool_name="propose_action",
        arguments=args.model_dump(mode="json"),
        basis=args.basis,
        summary=summary,
    )
    return _created(operation)


def execute_propose_status_change(
    db: Session,
    user_id: UUID,
    args: ProposeStatusChangeArgs,
) -> dict[str, object]:
    item = actions_repo.get_action_for_user(db, user_id=user_id, action_id=args.action_id)
    if item is None:
        return {"created": False, "error": "action_not_found"}
    if not proposed_change_is_allowed(item.status, args.change):
        return {"created": False, "error": "invalid_status_transition"}
    summary = f"把「{item.title}」改为{args.change}"
    operation = _insert(
        db,
        user_id=user_id,
        tool_name="propose_status_change",
        arguments=args.model_dump(mode="json"),
        basis=args.basis,
        summary=summary,
    )
    return _created(operation)


def _insert(
    db: Session,
    *,
    user_id: UUID,
    tool_name: str,
    arguments: dict[str, object],
    basis: str,
    summary: str,
) -> PendingOperation:
    operation = PendingOperation(
        id=uuid4(),
        user_id=user_id,
        run_id=current_run_id(),
        tool_name=tool_name,
        arguments=arguments,
        basis=basis,
        summary=summary,
        status="pending",
        expires_at=datetime.now(UTC) + PENDING_TTL,
    )
    db.add(operation)
    db.flush()
    return operation


def _created(operation: PendingOperation) -> dict[str, object]:
    return {
        "created": True,
        "id": str(operation.id),
        "tool_name": operation.tool_name,
        "summary": operation.summary,
        "basis": operation.basis,
        "expires_at": operation.expires_at.isoformat(),
    }


propose_action_tool = ToolSpec(
    name="propose_action",
    description=(
        "提议为当前用户的某个已保留问题创建行动项。"
        "只生成待确认操作，不会直接写入行动项。人确认后才会创建。"
    ),
    args_model=ProposeActionArgs,
    handler=execute_propose_action,
)

propose_status_change_tool = ToolSpec(
    name="propose_status_change",
    description=(
        "提议修改当前用户某个行动项的状态：开始、重新打开、取消、验收通过或驳回。"
        "只生成待确认操作，不会直接改状态。人确认后才会执行。"
    ),
    args_model=ProposeStatusChangeArgs,
    handler=execute_propose_status_change,
)
