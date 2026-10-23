from uuid import uuid4

import pytest

from app.agent.loop import run_agent
from app.agent.tools.registry import ToolRegistry
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.providers.llm import ChatWithToolsResult, LlmError, ToolCall


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
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


def test_answer_writes_one_llm_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.loop.chat_with_tools",
        lambda messages, tools: _reply("查不到相关复盘。"),
    )
    session = _Session()
    result = run_agent(
        session,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "今天天气如何"}],
        registry=ToolRegistry(),
    )
    runs = _runs(session)
    steps = _steps(session)
    assert result.status == "answered"
    assert len(runs) == 1
    assert runs[0].status == "answered"
    assert runs[0].kind == "chat"
    assert runs[0].output == "查不到相关复盘。"
    assert runs[0].prompt_tokens == 3
    assert runs[0].completion_tokens == 2
    assert runs[0].duration_ms >= 0
    assert runs[0].input == [{"role": "user", "content": "今天天气如何"}]
    assert len(steps) == 1
    assert steps[0].step_index == 1
    assert steps[0].step_type == "llm"
    assert steps[0].tool_name is None
    assert steps[0].result_summary == "查不到相关复盘。"
    assert steps[0].prompt_tokens == 3
    assert steps[0].duration_ms >= 0


def test_tool_step_stores_name_arguments_and_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(
        [
            _reply(
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="search_retro_content",
                        arguments={"query": "部署失败"},
                    )
                ]
            ),
            _reply("部署失败是因为配置写错。"),
        ]
    )
    monkeypatch.setattr("app.agent.loop.chat_with_tools", lambda messages, tools: next(replies))
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {"ok": True, "data": {"hits": [{"excerpt": "配置写错"}]}},
    )
    session = _Session()
    run_agent(
        session,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "部署为什么失败"}],
        registry=ToolRegistry(),
    )
    steps = _steps(session)
    assert [step.step_type for step in steps] == ["llm", "tool", "llm"]
    tool_step = steps[1]
    assert tool_step.tool_name == "search_retro_content"
    assert tool_step.arguments == {"query": "部署失败"}
    assert tool_step.error is None
    assert "配置写错" in (tool_step.result_summary or "")
    assert tool_step.prompt_tokens == 0
    assert tool_step.duration_ms >= 0
    assert _runs(session)[0].prompt_tokens == 6


def test_unexecuted_last_tool_call_is_not_a_tool_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.loop.chat_with_tools",
        lambda messages, tools: _reply(
            tool_calls=[
                ToolCall(id="call_x", name="search_retro_content", arguments={"query": "部署"})
            ]
        ),
    )
    executed = {"count": 0}

    def fake_execute(*args, **kwargs):
        executed["count"] += 1
        return {"ok": True, "data": {"hits": []}}

    monkeypatch.setattr("app.agent.loop.execute_tool", fake_execute)
    session = _Session()
    result = run_agent(
        session,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "一直查"}],
        registry=ToolRegistry(),
        max_steps=4,
    )
    tool_steps = [step for step in _steps(session) if step.step_type == "tool"]
    assert result.status == "max_steps"
    assert executed["count"] == 3
    assert len(tool_steps) == 3
    assert _steps(session)[-1].step_type == "llm"
    assert _runs(session)[0].status == "max_steps"


def test_llm_error_still_raises_and_keeps_earlier_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def chat(messages, tools):
        calls["count"] += 1
        if calls["count"] == 1:
            return _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="list_actions", arguments={"focus": "overdue"})
                ]
            )
        raise LlmError("llm_timeout")

    monkeypatch.setattr("app.agent.loop.chat_with_tools", chat)
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {"ok": True, "data": {"items": []}},
    )
    session = _Session()
    with pytest.raises(LlmError):
        run_agent(
            session,  # type: ignore[arg-type]
            user_id=uuid4(),
            messages=[{"role": "user", "content": "有哪些逾期"}],
            registry=ToolRegistry(),
        )
    steps = _steps(session)
    assert _runs(session)[0].status == "error"
    assert _runs(session)[0].output is None
    assert [step.step_type for step in steps] == ["llm", "tool", "llm"]
    assert steps[1].tool_name == "list_actions"
    assert steps[2].error == "llm_timeout"


def test_without_a_session_nothing_is_written(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.loop.chat_with_tools",
        lambda messages, tools: _reply("没有记录。"),
    )
    result = run_agent(
        None,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "你好"}],
        registry=ToolRegistry(),
    )
    assert result.status == "answered"
    assert result.answer == "没有记录。"


def _runs(session: _Session) -> list[AgentRun]:
    return [obj for obj in session.added if isinstance(obj, AgentRun)]


def _steps(session: _Session) -> list[AgentStep]:
    return [obj for obj in session.added if isinstance(obj, AgentStep)]
