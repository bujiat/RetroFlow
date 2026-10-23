import json
from uuid import uuid4

import pytest

from app.agent.loop import run_agent
from app.agent.tools.registry import ToolRegistry
from app.providers.llm import ChatWithToolsResult, LlmError, ToolCall


class _ScriptedChat:
    def __init__(self, replies: list[ChatWithToolsResult]) -> None:
        self.replies = replies
        self.calls: list[list[dict[str, object]]] = []

    def __call__(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ChatWithToolsResult:
        self.calls.append(messages)
        return self.replies[len(self.calls) - 1]


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


def test_answers_without_calling_a_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _ScriptedChat([_reply("查不到相关复盘。")])
    monkeypatch.setattr("app.agent.loop.chat_with_tools", chat)
    result = run_agent(
        None,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "今天天气如何"}],
        registry=ToolRegistry(),
    )
    assert result.status == "answered"
    assert result.answer == "查不到相关复盘。"
    assert result.steps == []
    assert result.prompt_tokens == 3
    assert len(chat.calls) == 1


def test_runs_tool_then_answers_with_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _ScriptedChat(
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
    monkeypatch.setattr("app.agent.loop.chat_with_tools", chat)
    seen: list[tuple[str, dict[str, object]]] = []

    def fake_execute(db, *, user_id, name, arguments, registry):
        seen.append((name, arguments))
        return {"ok": True, "data": {"hits": [{"excerpt": "配置写错"}]}}

    monkeypatch.setattr("app.agent.loop.execute_tool", fake_execute)
    result = run_agent(
        None,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "部署为什么失败"}],
        registry=ToolRegistry(),
    )
    assert result.status == "answered"
    assert result.answer == "部署失败是因为配置写错。"
    assert seen == [("search_retro_content", {"query": "部署失败"})]
    assert result.steps[0].result["ok"] is True
    second_messages = chat.calls[1]
    tool_message = second_messages[-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_1"
    assert "配置写错" in tool_message["content"]
    assistant_message = second_messages[-2]
    assert assistant_message["role"] == "assistant"
    assert assistant_message["tool_calls"][0]["function"]["name"] == "search_retro_content"
    arguments = json.loads(assistant_message["tool_calls"][0]["function"]["arguments"])
    assert arguments == {"query": "部署失败"}


def test_tool_error_is_sent_back_to_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _ScriptedChat(
        [
            _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="search_retro_content", arguments={"query": "部署"})
                ]
            ),
            _reply("检索暂时不可用。"),
        ]
    )
    monkeypatch.setattr("app.agent.loop.chat_with_tools", chat)
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {"ok": False, "error": {"code": "tool_failed", "message": "embedding_timeout"}},
    )
    result = run_agent(
        None,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "部署为什么失败"}],
        registry=ToolRegistry(),
    )
    assert result.status == "answered"
    assert result.answer == "检索暂时不可用。"
    payload = json.loads(chat.calls[1][-1]["content"])
    assert payload["error"]["code"] == "tool_failed"


def test_stops_when_the_model_keeps_calling_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = [
        _reply(
            tool_calls=[
                ToolCall(id=f"call_{index}", name="search_retro_content", arguments={"query": "部署"})
            ]
        )
        for index in range(4)
    ]
    chat = _ScriptedChat(calls)
    monkeypatch.setattr("app.agent.loop.chat_with_tools", chat)
    executed = {"count": 0}

    def fake_execute(*args, **kwargs):
        executed["count"] += 1
        return {"ok": True, "data": {"hits": []}}

    monkeypatch.setattr("app.agent.loop.execute_tool", fake_execute)
    result = run_agent(
        None,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "一直查"}],
        registry=ToolRegistry(),
        max_steps=4,
    )
    assert result.status == "max_steps"
    assert result.answer == "已达到最大步数，已停止。"
    assert len(chat.calls) == 4
    assert executed["count"] == 3
    assert len(result.steps) == 3


def test_stops_after_two_consecutive_tool_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _ScriptedChat(
        [
            _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="search_retro_content", arguments={"query": "部署"})
                ]
            ),
            _reply(
                tool_calls=[
                    ToolCall(id="call_2", name="search_retro_content", arguments={"query": "部署"})
                ]
            ),
            _reply("这条回答不应该出现。"),
        ]
    )
    monkeypatch.setattr("app.agent.loop.chat_with_tools", chat)
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {
            "ok": False,
            "error": {"code": "tool_failed", "message": "embedding_timeout"},
        },
    )
    result = run_agent(
        None,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "部署为什么失败"}],
        registry=ToolRegistry(),
    )
    assert result.status == "tool_failures"
    assert result.answer == "工具连续失败，已停止。"
    assert len(result.steps) == 2
    assert len(chat.calls) == 2


def test_a_success_resets_the_consecutive_failure_count(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _ScriptedChat(
        [
            _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="search_retro_content", arguments={"query": "部署"})
                ]
            ),
            _reply(
                tool_calls=[
                    ToolCall(id="call_2", name="search_retro_content", arguments={"query": "回滚"})
                ]
            ),
            _reply(
                tool_calls=[
                    ToolCall(id="call_3", name="search_retro_content", arguments={"query": "配置"})
                ]
            ),
            _reply("配置写错。"),
        ]
    )
    monkeypatch.setattr("app.agent.loop.chat_with_tools", chat)
    outcomes = iter(
        [
            {"ok": False, "error": {"code": "tool_failed", "message": "embedding_timeout"}},
            {"ok": True, "data": {"hits": []}},
            {"ok": False, "error": {"code": "tool_failed", "message": "embedding_timeout"}},
        ]
    )
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: next(outcomes),
    )
    result = run_agent(
        None,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "部署为什么失败"}],
        registry=ToolRegistry(),
    )
    assert result.status == "answered"
    assert result.answer == "配置写错。"
    assert len(result.steps) == 3


def test_one_tool_failure_still_returns_to_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _ScriptedChat(
        [
            _reply(
                tool_calls=[
                    ToolCall(id="call_1", name="search_retro_content", arguments={"query": "部署"})
                ]
            ),
            _reply("检索暂时不可用。"),
        ]
    )
    monkeypatch.setattr("app.agent.loop.chat_with_tools", chat)
    monkeypatch.setattr(
        "app.agent.loop.execute_tool",
        lambda *args, **kwargs: {
            "ok": False,
            "error": {"code": "invalid_arguments", "message": "参数不符合工具定义"},
        },
    )
    result = run_agent(
        None,  # type: ignore[arg-type]
        user_id=uuid4(),
        messages=[{"role": "user", "content": "部署为什么失败"}],
        registry=ToolRegistry(),
    )
    assert result.status == "answered"
    assert result.answer == "检索暂时不可用。"
    assert len(chat.calls) == 2


def test_llm_error_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(messages, tools):
        raise LlmError("llm_timeout")

    monkeypatch.setattr("app.agent.loop.chat_with_tools", fail)
    with pytest.raises(LlmError) as exc:
        run_agent(
            None,  # type: ignore[arg-type]
            user_id=uuid4(),
            messages=[{"role": "user", "content": "部署为什么失败"}],
            registry=ToolRegistry(),
        )
    assert exc.value.message == "llm_timeout"
