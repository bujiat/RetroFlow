from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.agent.loop import run_agent
from app.agent.tools.executor import execute_tool
from app.models.action_item import ActionItem
from app.models.agent_run import AgentRun
from app.models.pending_operation import PendingOperation
from app.providers.llm import ChatWithToolsResult, ToolCall
from app.schemas.actions import ActionItemOut
from app.services.pending import confirm_operation, reject_operation


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def get(self, model: type, ident: object) -> object | None:
        for obj in self.added:
            if isinstance(obj, model) and getattr(obj, "id", None) == ident:
                return obj
        return None


def test_propose_action_does_not_create_an_action(monkeypatch: pytest.MonkeyPatch) -> None:
    problem_id = uuid4()
    monkeypatch.setattr(
        "app.agent.tools.proposals.analysis_repo.get_problem_for_user",
        lambda *args, **kwargs: SimpleNamespace(id=problem_id, disposition="kept"),
    )
    session = _Session()
    result = execute_tool(
        session,  # type: ignore[arg-type]
        user_id=uuid4(),
        name="propose_action",
        arguments=_action_args(problem_id),
    )
    assert result["ok"] is True
    assert result["data"]["created"] is True
    assert not any(isinstance(obj, ActionItem) for obj in session.added)
    assert any(isinstance(obj, PendingOperation) for obj in session.added)


def test_run_keeps_the_proposal_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    problem_id = uuid4()
    user_id = uuid4()
    monkeypatch.setattr(
        "app.agent.tools.proposals.analysis_repo.get_problem_for_user",
        lambda *args, **kwargs: SimpleNamespace(id=problem_id, disposition="kept"),
    )
    replies = iter(
        [
            _reply(
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="propose_action",
                        arguments=_action_args(problem_id),
                    )
                ]
            ),
            _reply('{"status":"insufficient_evidence","answer":"等你确认。","citation_ids":[]}'),
        ]
    )
    monkeypatch.setattr("app.agent.loop.chat_with_tools", lambda messages, tools: next(replies))
    session = _Session()
    result = run_agent(
        session,  # type: ignore[arg-type]
        user_id=user_id,
        messages=[{"role": "user", "content": "帮我建一条行动项"}],
    )
    pending = [obj for obj in session.added if isinstance(obj, PendingOperation)]
    runs = [obj for obj in session.added if isinstance(obj, AgentRun)]
    assert result.status == "answered"
    assert len(pending) == 1
    assert pending[0].status == "pending"
    assert pending[0].run_id == runs[0].id
    assert not any(isinstance(obj, ActionItem) for obj in session.added)


def test_confirm_creates_the_action_and_second_confirm_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    operation = _operation(user_id)
    session = _Session()
    session.add(operation)
    created = {"count": 0}

    def fake_create(db, user, **kwargs):
        created["count"] += 1
        db.commit()
        return _action_out(kwargs["problem_id"])

    monkeypatch.setattr("app.services.pending.actions_service.create_action_for_problem", fake_create)
    user = SimpleNamespace(id=user_id)
    operation_out, action = confirm_operation(session, user, operation.id)  # type: ignore[arg-type]
    assert action.title == "补上检查清单"
    assert operation_out.status == "approved"
    assert created["count"] == 1
    with pytest.raises(HTTPException) as exc:
        confirm_operation(session, user, operation.id)  # type: ignore[arg-type]
    assert exc.value.status_code == 409
    assert exc.value.detail == {"code": "operation_already_resolved"}
    assert created["count"] == 1


def test_confirm_rejects_another_users_operation() -> None:
    operation = _operation(uuid4())
    session = _Session()
    session.add(operation)
    with pytest.raises(HTTPException) as exc:
        confirm_operation(session, SimpleNamespace(id=uuid4()), operation.id)  # type: ignore[arg-type]
    assert exc.value.status_code == 404
    assert operation.status == "pending"


def test_confirm_rejects_an_expired_operation() -> None:
    user_id = uuid4()
    operation = _operation(user_id)
    operation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    session = _Session()
    session.add(operation)
    with pytest.raises(HTTPException) as exc:
        confirm_operation(session, SimpleNamespace(id=user_id), operation.id)  # type: ignore[arg-type]
    assert exc.value.status_code == 409
    assert exc.value.detail == {"code": "operation_expired"}
    assert operation.status == "expired"
    assert session.commits == 1


def test_confirm_keeps_pending_when_the_status_machine_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    operation = _operation(user_id)
    operation.tool_name = "propose_status_change"
    operation.arguments = {
        "action_id": str(uuid4()),
        "change": "verify",
        "basis": "证据对得上",
        "reason": None,
    }
    session = _Session()
    session.add(operation)

    def refuse(db, user, arguments):
        raise HTTPException(status_code=409, detail={"code": "invalid_status_transition"})

    monkeypatch.setattr(
        "app.services.pending.actions_service.apply_proposed_status_change",
        refuse,
    )
    with pytest.raises(HTTPException) as exc:
        confirm_operation(session, SimpleNamespace(id=user_id), operation.id)  # type: ignore[arg-type]
    assert exc.value.detail == {"code": "invalid_status_transition"}
    assert operation.status == "pending"
    assert operation.resolved_at is None


def test_reject_then_confirm_is_rejected() -> None:
    user_id = uuid4()
    operation = _operation(user_id)
    session = _Session()
    session.add(operation)
    user = SimpleNamespace(id=user_id)
    rejected = reject_operation(session, user, operation.id)  # type: ignore[arg-type]
    assert rejected.status == "rejected"
    with pytest.raises(HTTPException) as exc:
        confirm_operation(session, user, operation.id)  # type: ignore[arg-type]
    assert exc.value.detail == {"code": "operation_already_resolved"}


def test_invalid_transition_does_not_insert_a_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.tools.proposals.actions_repo.get_action_for_user",
        lambda *args, **kwargs: SimpleNamespace(status="cancelled", title="已取消"),
    )
    session = _Session()
    result = execute_tool(
        session,  # type: ignore[arg-type]
        user_id=uuid4(),
        name="propose_status_change",
        arguments={
            "action_id": str(uuid4()),
            "change": "start",
            "basis": "想重新开始",
        },
    )
    assert result["data"]["created"] is False
    assert result["data"]["error"] == "invalid_status_transition"
    assert session.added == []


def _action_args(problem_id: object) -> dict[str, object]:
    return {
        "problem_id": str(problem_id),
        "title": "补上检查清单",
        "description": "发布前核对配置",
        "owner": "李玉",
        "due_date": "2026-11-01",
        "success_criteria": "清单被执行过一次",
        "basis": "这个问题重复出现",
    }


def _operation(user_id: object) -> PendingOperation:
    return PendingOperation(
        id=uuid4(),
        user_id=user_id,  # type: ignore[arg-type]
        run_id=None,
        tool_name="propose_action",
        arguments=_action_args(uuid4()),
        basis="这个问题重复出现",
        summary="创建行动项：补上检查清单",
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _action_out(problem_id: object) -> ActionItemOut:
    return ActionItemOut(
        id=uuid4(),
        retro_id=uuid4(),
        problem_occurrence_id=problem_id,  # type: ignore[arg-type]
        title="补上检查清单",
        description="发布前核对配置",
        owner="李玉",
        due_date=datetime(2026, 11, 1).date(),
        success_criteria="清单被执行过一次",
        status="open",
        created_at=datetime.now(UTC),
    )


def _reply(
    content: str | None = None,
    tool_calls: list[ToolCall] | None = None,
) -> ChatWithToolsResult:
    return ChatWithToolsResult(
        content=content,
        tool_calls=tool_calls or [],
        prompt_tokens=2,
        completion_tokens=1,
    )
