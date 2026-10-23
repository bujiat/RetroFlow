from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolSpec
from app.agent.tools.users import load_user
from app.schemas.actions import ActionEventOut, ActionItemOut
from app.services import actions as actions_service

MAX_ACTION_ITEMS = 20
_OPEN_WORK = frozenset({"open", "in_progress", "evidence_submitted"})
_STATUS_RANK = {
    "open": 0,
    "in_progress": 1,
    "evidence_submitted": 2,
    "verified": 3,
    "cancelled": 4,
}


class ListActionsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus: Literal["open_work", "overdue", "due_this_week", "awaiting_verify", "all"] = Field(
        default="open_work",
        description=(
            "open_work：未完成和待验收，包含已逾期；"
            "overdue：只看已逾期；"
            "due_this_week：本周到期且未完成；"
            "awaiting_verify：已交证据、等待验收；"
            "all：包含已验收和已取消。"
        ),
    )


class GetActionHistoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: UUID = Field(description="行动项 id。使用 list_actions 返回的 id，形如 action:<uuid>。")

    @field_validator("action_id", mode="before")
    @classmethod
    def strip_action_prefix(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("action:"):
            return value.removeprefix("action:")
        return value


def execute_list_actions(
    db: Session,
    user_id: UUID,
    args: ListActionsArgs,
) -> dict[str, object]:
    user = load_user(db, user_id)
    if user is None:
        return {"focus": args.focus, "items": [], "limited": False}
    if args.focus == "overdue":
        rows = actions_service.get_my_week(db, user).overdue
    elif args.focus == "due_this_week":
        rows = actions_service.get_my_week(db, user).due_this_week
    elif args.focus == "awaiting_verify":
        rows = actions_service.get_my_week(db, user).awaiting_verify
    else:
        rows = actions_service.list_actions(db, user)
        if args.focus == "open_work":
            rows = [row for row in rows if row.status in _OPEN_WORK]
        else:
            rows = sorted(rows, key=lambda row: (_STATUS_RANK.get(row.status, 9), row.due_date))
    limited = len(rows) > MAX_ACTION_ITEMS
    return {
        "focus": args.focus,
        "items": [_action_brief(row) for row in rows[:MAX_ACTION_ITEMS]],
        "limited": limited,
    }


def execute_get_action_history(
    db: Session,
    user_id: UUID,
    args: GetActionHistoryArgs,
) -> dict[str, object]:
    action_id = f"action:{args.action_id}"
    user = load_user(db, user_id)
    if user is None:
        return {"found": False, "action_id": action_id, "events": []}
    try:
        rows = actions_service.list_events(db, user, args.action_id)
    except HTTPException:
        return {"found": False, "action_id": action_id, "events": []}
    return {
        "found": True,
        "action_id": action_id,
        "events": [_event_brief(row) for row in rows],
    }


def _action_brief(item: ActionItemOut) -> dict[str, object]:
    return {
        "id": f"action:{item.id}",
        "title": item.title,
        "owner": item.owner,
        "due_date": item.due_date.isoformat(),
        "status": item.status,
        "success_criteria": item.success_criteria[:200],
    }


def _event_brief(event: ActionEventOut) -> dict[str, object]:
    note = event.note[:300] if event.note else None
    evidence = event.evidence_text[:300] if event.evidence_text else None
    return {
        "event_type": event.event_type,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "note": note,
        "evidence_text": evidence,
        "evidence_url": event.evidence_url,
        "created_at": event.created_at.isoformat(),
    }


list_actions_tool = ToolSpec(
    name="list_actions",
    description=(
        "列出当前用户自己的行动项。"
        "问逾期、本周到期、待验收或全部行动项时使用。"
        "不用于搜索会议原文。"
    ),
    args_model=ListActionsArgs,
    handler=execute_list_actions,
)

get_action_history_tool = ToolSpec(
    name="get_action_history",
    description=(
        "查看某一个行动项的状态变化和证据记录。"
        "先用 list_actions 拿到 id，再调用本工具。"
        "行动项不属于当前用户时 found 为 false。"
    ),
    args_model=GetActionHistoryArgs,
    handler=execute_get_action_history,
)
