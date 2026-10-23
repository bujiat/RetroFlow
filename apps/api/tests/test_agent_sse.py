import asyncio
import json
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.agent_run import AgentRun
from app.providers.llm import ChatWithToolsResult, LlmError, ToolCall
from app.routers.agent import agent_chat_route
from app.schemas.agent import AgentChatRequest
from app.services.agent_chat import iter_sse, stream_chat


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

    def close(self) -> None:
        return None

    def get(self, model: type, ident: object) -> object | None:
        for obj in self.added:
            if isinstance(obj, model) and getattr(obj, "id", None) == ident:
                return obj
        return None


def _reply(
    content: str | None = None,
    tool_calls: list[ToolCall] | None = None,
) -> ChatWithToolsResult:
    return ChatWithToolsResult(
        content=content,
        tool_calls=tool_calls or [],
        prompt_tokens=3,
        completion_tokens=2,
    )


def _final(answer: str, citation_ids: list[str]) -> str:
    return json.dumps(
        {"status": "answered", "answer": answer, "citation_ids": citation_ids},
        ensure_ascii=False,
    )


def _events(frames: list[str]) -> list[tuple[str, dict[str, object]]]:
    parsed: list[tuple[str, dict[str, object]]] = []
    for frame in frames:
        lines = frame.strip().split("\n")
        name = lines[0].removeprefix("event: ")
        data = json.loads(lines[1].removeprefix("data: "))
        parsed.append((name, data))
    return parsed


def _user_id():
    return uuid4()


def test_tool_events_leave_before_the_next_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    chunk_id = uuid4()
    retro_id = uuid4()
    cid = f"chunk:{chunk_id}"
    invented = f"chunk:{uuid4()}"
    calls = {"n": 0}
    replies = iter(
        [
            _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="search_retro_content", arguments={"query": "部署失败"})
                ]
            ),
            _reply(_final("配置写错。", [cid, invented])),
        ]
    )

    def model(messages, tools):
        calls["n"] += 1
        return next(replies)

    monkeypatch.setattr("app.agent.loop.chat_with_tools", model)
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {
            "ok": True,
            "data": {
                "hits": [
                    {
                        "id": cid,
                        "retro_id": str(retro_id),
                        "score": 0.91,
                        "excerpt": "配置写错导致部署失败",
                    }
                ]
            },
        },
    )
    session = _Session()
    seen_at: list[int] = []
    frames: list[str] = []
    for frame in iter_sse(session, _user_id(), AgentChatRequest(question="部署为什么失败")):
        frames.append(frame)
        if frame.startswith("event: tool_call"):
            seen_at.append(calls["n"])

    names = [name for name, _data in _events(frames)]
    assert names == ["run_started", "tool_call", "tool_result", "answer", "done"]
    assert seen_at == [1]
    assert calls["n"] == 2
    answer = _events(frames)[3][1]
    assert answer["status"] == "answered"
    assert answer["answer"] == "配置写错。"
    assert [item["id"] for item in answer["citations"]] == [cid]
    assert session.commits == 1
    assert _run(session).status == "answered"


def test_stream_emits_the_tool_result_while_the_next_call_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = threading.Event()
    calls = {"n": 0, "timed_out": False}
    replies = iter(
        [
            _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="list_actions", arguments={"focus": "overdue"})
                ]
            ),
            _reply(_final("没有逾期。", [])),
        ]
    )

    def model(messages, tools):
        calls["n"] += 1
        if calls["n"] == 2 and not gate.wait(timeout=2):
            calls["timed_out"] = True
        return next(replies)

    monkeypatch.setattr("app.agent.loop.chat_with_tools", model)
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {"ok": True, "data": {"items": [], "limited": False}},
    )
    session = _Session()

    async def collect() -> list[str]:
        frames: list[str] = []
        async for frame in stream_chat(
            _user_id(),
            AgentChatRequest(question="有哪些逾期"),
            open_session=lambda: session,
        ):
            frames.append(frame)
            if frame.startswith("event: tool_result"):
                gate.set()
        return frames

    frames = asyncio.run(collect())
    names = [name for name, _data in _events(frames)]
    assert calls["timed_out"] is False
    assert names[:3] == ["run_started", "tool_call", "tool_result"]
    assert names[-2:] == ["answer", "done"]
    assert _events(frames)[-2][1]["status"] == "insufficient_evidence"


def test_llm_error_pushes_an_error_event_and_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def model(messages, tools):
        calls["n"] += 1
        if calls["n"] == 1:
            return _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="search_retro_content", arguments={"query": "部署"})
                ]
            )
        raise LlmError("llm_timeout")

    monkeypatch.setattr("app.agent.loop.chat_with_tools", model)
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {"ok": True, "data": {"hits": []}},
    )
    session = _Session()
    frames = list(iter_sse(session, _user_id(), AgentChatRequest(question="部署为什么失败")))
    names = [name for name, _data in _events(frames)]
    assert names == ["run_started", "tool_call", "tool_result", "error", "done"]
    assert _events(frames)[3][1] == {"code": "llm_timeout"}
    assert _events(frames)[4][1] == {"ok": False}
    assert session.commits == 1
    assert _run(session).status == "error"


def test_pending_operation_is_its_own_event(monkeypatch: pytest.MonkeyPatch) -> None:
    operation_id = uuid4()
    monkeypatch.setattr(
        "app.agent.loop.chat_with_tools",
        lambda messages, tools: _reply(
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="propose_action",
                    arguments={"title": "补上发布检查"},
                )
            ]
        )
        if not any(message.get("role") == "tool" for message in messages)
        else _reply(_final("已生成待确认操作。", [])),
    )
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {
            "ok": True,
            "data": {
                "created": True,
                "id": str(operation_id),
                "tool_name": "propose_action",
                "summary": "补上发布检查",
                "expires_at": "2026-10-24T00:00:00+00:00",
            },
        },
    )
    frames = list(iter_sse(_Session(), _user_id(), AgentChatRequest(question="帮我记一条行动")))
    parsed = _events(frames)
    names = [name for name, _data in parsed]
    assert names == [
        "run_started",
        "tool_call",
        "tool_result",
        "pending_operation",
        "answer",
        "done",
    ]
    assert parsed[3][1]["id"] == str(operation_id)
    assert parsed[3][1]["tool_name"] == "propose_action"


def test_invalid_final_json_pushes_an_error_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.loop.chat_with_tools",
        lambda messages, tools: _reply("我直接说配置写错了。"),
    )
    session = _Session()
    frames = list(iter_sse(session, _user_id(), AgentChatRequest(question="部署为什么失败")))
    parsed = _events(frames)
    assert [name for name, _data in parsed] == ["run_started", "error", "done"]
    assert parsed[1][1] == {"code": "assistant_schema_invalid"}
    assert parsed[2][1] == {"ok": False}
    assert session.commits == 1
    assert _run(session).status == "invalid_answer"


def test_blank_question_is_rejected_before_the_stream() -> None:
    user = SimpleNamespace(id=uuid4())
    with pytest.raises(HTTPException) as exc:
        agent_chat_route(AgentChatRequest(question="  "), user)  # type: ignore[arg-type]
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "question_too_short"}


def _run(session: _Session) -> AgentRun:
    runs = [obj for obj in session.added if isinstance(obj, AgentRun)]
    assert len(runs) == 1
    return runs[0]
