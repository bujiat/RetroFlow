import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep

SUMMARY_LIMIT = 500
ARGUMENTS_LIMIT = 2000

StepType = Literal["llm", "tool"]


@dataclass(frozen=True)
class TraceEvent:
    step_type: StepType
    tool_name: str | None
    arguments: dict[str, object] | None
    result_summary: str | None
    error: str | None
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int


def summarize(value: object, limit: int = SUMMARY_LIMIT) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    return text[:limit]


def begin_agent_run(
    db: Session,
    *,
    user_id: UUID,
    kind: str,
    messages: list[dict[str, object]],
    started_at: datetime,
) -> AgentRun:
    """Insert the run row before tools execute, so a proposal can point at it."""
    run = AgentRun(
        id=uuid4(),
        user_id=user_id,
        kind=kind,
        status="running",
        input=_json_ready(messages),
        output=None,
        prompt_tokens=0,
        completion_tokens=0,
        duration_ms=0,
        created_at=started_at,
    )
    db.add(run)
    db.flush()
    return run


def finish_agent_run(
    db: Session,
    run: AgentRun,
    *,
    status: str,
    output: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: int,
    events: list[TraceEvent],
) -> AgentRun:
    """Fill in the outcome and steps. Does not commit."""
    run.status = status
    run.output = output
    run.prompt_tokens = prompt_tokens
    run.completion_tokens = completion_tokens
    run.duration_ms = duration_ms
    for index, event in enumerate(events, start=1):
        db.add(
            AgentStep(
                id=uuid4(),
                run_id=run.id,
                step_index=index,
                step_type=event.step_type,
                tool_name=event.tool_name,
                arguments=_arguments(event.arguments),
                result_summary=event.result_summary,
                error=event.error,
                prompt_tokens=event.prompt_tokens,
                completion_tokens=event.completion_tokens,
                duration_ms=event.duration_ms,
            )
        )
    db.flush()
    return run


def save_agent_trace(
    db: Session,
    *,
    user_id: UUID,
    kind: str,
    status: str,
    messages: list[dict[str, object]],
    output: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: int,
    started_at: datetime,
    events: list[TraceEvent],
) -> AgentRun:
    """Write one run and its steps into the current transaction. Does not commit."""
    run = begin_agent_run(
        db,
        user_id=user_id,
        kind=kind,
        messages=messages,
        started_at=started_at,
    )
    return finish_agent_run(
        db,
        run,
        status=status,
        output=output,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        duration_ms=duration_ms,
        events=events,
    )


def _arguments(arguments: dict[str, object] | None) -> dict | None:
    if arguments is None:
        return None
    encoded = json.dumps(arguments, ensure_ascii=False, default=str)
    if len(encoded) <= ARGUMENTS_LIMIT:
        loaded = json.loads(encoded)
        if isinstance(loaded, dict):
            return loaded
    return {"truncated": True, "preview": encoded[:ARGUMENTS_LIMIT]}


def _json_ready(value: object) -> list:
    encoded = json.dumps(value, ensure_ascii=False, default=str)
    loaded = json.loads(encoded)
    if isinstance(loaded, list):
        return loaded
    return [{"truncated": True, "preview": encoded[:ARGUMENTS_LIMIT]}]
