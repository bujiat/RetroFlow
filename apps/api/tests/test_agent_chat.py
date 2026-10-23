import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.main import app
from app.models.agent_run import AgentRun
from app.providers.llm import ChatWithToolsResult, LlmError, ToolCall
from app.schemas.agent import AgentChatRequest
from app.services.agent_chat import chat


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


def _final(status: str, answer: str, citation_ids: list[str]) -> str:
    return json.dumps(
        {"status": status, "answer": answer, "citation_ids": citation_ids},
        ensure_ascii=False,
    )


def test_routes_keep_the_old_assistant_and_add_agent_chat() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/assistant/query" in paths
    assert "post" in paths["/api/v1/agent/chat"]


def test_cited_chunk_from_the_tool_result_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    chunk_id = uuid4()
    retro_id = uuid4()
    cid = f"chunk:{chunk_id}"
    replies = iter(
        [
            _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="search_retro_content", arguments={"query": "部署失败"})
                ]
            ),
            _reply(_final("answered", "配置写错。", [cid, f"chunk:{uuid4()}"])),
        ]
    )
    monkeypatch.setattr("app.agent.loop.chat_with_tools", lambda messages, tools: next(replies))
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
    response = chat(session, _user(), AgentChatRequest(question="部署为什么失败"))  # type: ignore[arg-type]
    assert response.status == "answered"
    assert response.answer == "配置写错。"
    assert [item.id for item in response.citations] == [cid]
    assert response.citations[0].source_type == "chunk"
    assert response.citations[0].retro_id == retro_id
    assert session.commits == 1
    assert _run(session).status == "answered"
    assert _run(session).output == "配置写错。"
    assert response.run_id == _run(session).id


def test_invented_citation_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(
        [
            _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="search_retro_content", arguments={"query": "部署"})
                ]
            ),
            _reply(_final("answered", "我猜是配置问题。", [f"chunk:{uuid4()}"])),
        ]
    )
    monkeypatch.setattr("app.agent.loop.chat_with_tools", lambda messages, tools: next(replies))
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {"ok": True, "data": {"hits": []}},
    )
    session = _Session()
    response = chat(session, _user(), AgentChatRequest(question="部署为什么失败"))  # type: ignore[arg-type]
    assert response.status == "insufficient_evidence"
    assert response.citations == []
    assert _run(session).status == "insufficient_evidence"


def test_unrelated_question_can_refuse_without_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.loop.chat_with_tools",
        lambda messages, tools: _reply(
            _final("insufficient_evidence", "这和复盘改进无关。", [])
        ),
    )
    session = _Session()
    response = chat(session, _user(), AgentChatRequest(question="今天天气如何"))  # type: ignore[arg-type]
    assert response.status == "insufficient_evidence"
    assert response.answer == "这和复盘改进无关。"
    assert response.citations == []
    assert session.commits == 1


def test_tool_failures_do_not_invent_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.loop.chat_with_tools",
        lambda messages, tools: _reply(
            tool_calls=[
                ToolCall(id="call_x", name="search_retro_content", arguments={"query": "部署"})
            ]
        ),
    )
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {"ok": False, "error": {"code": "tool_failed", "message": "down"}},
    )
    session = _Session()
    response = chat(session, _user(), AgentChatRequest(question="部署为什么失败"))  # type: ignore[arg-type]
    assert response.status == "tool_failures"
    assert response.citations == []
    assert _run(session).status == "tool_failures"


def test_llm_error_commits_the_trace_and_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(messages, tools):
        raise LlmError("llm_timeout")

    monkeypatch.setattr("app.agent.loop.chat_with_tools", fail)
    session = _Session()
    with pytest.raises(HTTPException) as exc:
        chat(session, _user(), AgentChatRequest(question="部署为什么失败"))  # type: ignore[arg-type]
    assert exc.value.status_code == 502
    assert exc.value.detail == {"code": "llm_timeout"}
    assert session.commits == 1
    assert _run(session).status == "error"


def test_invalid_final_json_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.loop.chat_with_tools",
        lambda messages, tools: _reply("我直接说配置写错了。"),
    )
    session = _Session()
    with pytest.raises(HTTPException) as exc:
        chat(session, _user(), AgentChatRequest(question="部署为什么失败"))  # type: ignore[arg-type]
    assert exc.value.status_code == 502
    assert exc.value.detail == {"code": "assistant_schema_invalid"}
    assert session.commits == 1
    assert _run(session).status == "invalid_answer"


def test_max_steps_stops_without_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.loop.chat_with_tools",
        lambda messages, tools: _reply(
            tool_calls=[
                ToolCall(id="call_x", name="list_actions", arguments={"focus": "overdue"})
            ]
        ),
    )
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {"ok": True, "data": {"items": [], "limited": False}},
    )
    session = _Session()
    response = chat(session, _user(), AgentChatRequest(question="有哪些逾期"))  # type: ignore[arg-type]
    assert response.status == "max_steps"
    assert response.citations == []
    assert response.answer == "已达到最大步数，已停止。"


def test_blank_question_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        chat(_Session(), _user(), AgentChatRequest(question="  "))  # type: ignore[arg-type]
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "question_too_short"}


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _run(session: _Session) -> AgentRun:
    runs = [obj for obj in session.added if isinstance(obj, AgentRun)]
    assert len(runs) == 1
    return runs[0]
