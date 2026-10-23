import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.agent.context import bind_run
from app.agent.tools.executor import execute_tool
from app.agent.tools.registry import ToolRegistry, default_registry
from app.agent.tracing import TraceEvent, begin_agent_run, finish_agent_run, summarize
from app.providers.llm import ChatWithToolsResult, LlmError, ToolCall, chat_with_tools

MAX_AGENT_STEPS = 6
MAX_CONSECUTIVE_TOOL_FAILURES = 2

AgentStatus = Literal["answered", "max_steps", "tool_failures"]


@dataclass(frozen=True)
class AgentStep:
    tool_call_id: str
    name: str
    arguments: dict[str, object]
    result: dict[str, object]


@dataclass(frozen=True)
class AgentRunResult:
    status: AgentStatus
    answer: str | None
    steps: list[AgentStep]
    prompt_tokens: int
    completion_tokens: int
    run_id: UUID | None = None


@dataclass(frozen=True)
class StreamEvent:
    """One progress report emitted while the loop is still running."""

    name: Literal["run_started", "tool_call", "tool_result", "pending_operation"]
    data: dict[str, object]


def run_agent(
    db: Session,
    *,
    user_id: UUID,
    messages: list[dict[str, object]],
    registry: ToolRegistry | None = None,
    max_steps: int = MAX_AGENT_STEPS,
) -> AgentRunResult:
    """Let the model choose tools. The program runs them and feeds results back.

    One step is one model call. A tool error is returned to the model. Two
    failures in a row end the run. The last step never executes another tool.
    Model request failures still raise LlmError. When db is a real session, the
    run row is inserted first and finished at the end of this transaction.
    """
    outcome: AgentRunResult | None = None
    for item in iterate_agent(
        db,
        user_id=user_id,
        messages=messages,
        registry=registry,
        max_steps=max_steps,
    ):
        if isinstance(item, AgentRunResult):
            outcome = item
    if outcome is None:
        raise RuntimeError("agent run produced no result")
    return outcome


def iterate_agent(
    db: Session,
    *,
    user_id: UUID,
    messages: list[dict[str, object]],
    registry: ToolRegistry | None = None,
    max_steps: int = MAX_AGENT_STEPS,
) -> Iterator[StreamEvent | AgentRunResult]:
    """Same loop as run_agent, but each tool boundary is yielded immediately.

    The final item is the AgentRunResult. LlmError still propagates after the
    error step is stored.
    """
    tools = registry or default_registry
    history = list(messages)
    steps: list[AgentStep] = []
    events: list[TraceEvent] = []
    prompt_tokens = 0
    completion_tokens = 0
    consecutive_failures = 0
    schemas = tools.openai_tools()
    started_at = datetime.now(UTC)
    started = perf_counter()
    active_run = None
    if db is not None:
        active_run = begin_agent_run(
            db,
            user_id=user_id,
            kind="chat",
            messages=messages,
            started_at=started_at,
        )

    def persist(status: str, output: str | None) -> UUID | None:
        if active_run is None:
            return None
        finish_agent_run(
            db,
            active_run,
            status=status,
            output=output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=_elapsed_ms(started),
            events=events,
        )
        return active_run.id

    with bind_run(active_run.id if active_run is not None else None):
        if active_run is not None:
            yield StreamEvent("run_started", {"run_id": str(active_run.id)})
        for index in range(max_steps):
            llm_started = perf_counter()
            try:
                result = chat_with_tools(history, schemas)
            except LlmError as exc:
                events.append(
                    TraceEvent(
                        step_type="llm",
                        tool_name=None,
                        arguments=None,
                        result_summary=None,
                        error=exc.message,
                        prompt_tokens=0,
                        completion_tokens=0,
                        duration_ms=_elapsed_ms(llm_started),
                    )
                )
                persist("error", None)
                raise
            prompt_tokens += result.prompt_tokens
            completion_tokens += result.completion_tokens
            events.append(_llm_event(result, _elapsed_ms(llm_started)))
            if not result.tool_calls:
                answer = result.content
                yield _finish(
                    "answered",
                    answer,
                    steps,
                    prompt_tokens,
                    completion_tokens,
                    persist("answered", answer),
                )
                return
            history.append(_assistant_message(result))
            if index == max_steps - 1:
                break
            for call in result.tool_calls:
                yield StreamEvent(
                    "tool_call",
                    {"name": call.name, "arguments": call.arguments},
                )
                tool_started = perf_counter()
                tool_result = execute_tool(
                    db,
                    user_id=user_id,
                    name=call.name,
                    arguments=call.arguments,
                    registry=tools,
                )
                steps.append(
                    AgentStep(
                        tool_call_id=call.id,
                        name=call.name,
                        arguments=call.arguments,
                        result=tool_result,
                    )
                )
                events.append(_tool_event(call, tool_result, _elapsed_ms(tool_started)))
                history.append(_tool_message(call, tool_result))
                yield StreamEvent(
                    "tool_result",
                    {
                        "name": call.name,
                        "ok": tool_result.get("ok") is True,
                        "summary": summarize(tool_result),
                    },
                )
                pending = _pending_event(tool_result)
                if pending is not None:
                    yield pending
                if tool_result.get("ok") is True:
                    consecutive_failures = 0
                    continue
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_TOOL_FAILURES:
                    answer = "工具连续失败，已停止。"
                    yield _finish(
                        "tool_failures",
                        answer,
                        steps,
                        prompt_tokens,
                        completion_tokens,
                        persist("tool_failures", answer),
                    )
                    return

        answer = "已达到最大步数，已停止。"
        yield _finish(
            "max_steps",
            answer,
            steps,
            prompt_tokens,
            completion_tokens,
            persist("max_steps", answer),
        )


def _pending_event(tool_result: dict[str, object]) -> StreamEvent | None:
    if tool_result.get("ok") is not True:
        return None
    data = tool_result.get("data")
    if not isinstance(data, dict) or data.get("created") is not True:
        return None
    required = ("id", "tool_name", "summary", "expires_at")
    if any(data.get(key) in (None, "") for key in required):
        return None
    return StreamEvent(
        "pending_operation",
        {
            "id": str(data["id"]),
            "tool_name": str(data["tool_name"]),
            "summary": str(data["summary"]),
            "expires_at": str(data["expires_at"]),
        },
    )


def _finish(
    status: AgentStatus,
    answer: str | None,
    steps: list[AgentStep],
    prompt_tokens: int,
    completion_tokens: int,
    run_id: UUID | None,
) -> AgentRunResult:
    return AgentRunResult(
        status=status,
        answer=answer,
        steps=steps,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        run_id=run_id,
    )


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def _llm_event(result: ChatWithToolsResult, duration_ms: int) -> TraceEvent:
    if result.tool_calls:
        names = ", ".join(call.name for call in result.tool_calls)
        summary = summarize(f"tool_calls: {names}")
    else:
        summary = summarize(result.content or "")
    return TraceEvent(
        step_type="llm",
        tool_name=None,
        arguments=None,
        result_summary=summary,
        error=None,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        duration_ms=duration_ms,
    )


def _tool_event(call: ToolCall, result: dict[str, object], duration_ms: int) -> TraceEvent:
    error = None
    if result.get("ok") is not True:
        error = summarize(result.get("error"))
    return TraceEvent(
        step_type="tool",
        tool_name=call.name,
        arguments=call.arguments,
        result_summary=summarize(result),
        error=error,
        prompt_tokens=0,
        completion_tokens=0,
        duration_ms=duration_ms,
    )


def _assistant_message(result: ChatWithToolsResult) -> dict[str, object]:
    return {
        "role": "assistant",
        "content": result.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in result.tool_calls
        ],
    }


def _tool_message(call: ToolCall, result: dict[str, object]) -> dict[str, object]:
    return {
        "role": "tool",
        "tool_call_id": call.id,
        "content": json.dumps(result, ensure_ascii=False),
    }
