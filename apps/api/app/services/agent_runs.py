from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.user import User
from app.repositories import agent_runs as runs_repo
from app.schemas.agent import AgentRunDetail, AgentRunList, AgentRunSummary, AgentStepOut

QUESTION_PREVIEW = 160


def list_runs(db: Session, user: User) -> AgentRunList:
    rows = runs_repo.list_runs_for_user(db, user.id)
    limited = len(rows) > 50
    return AgentRunList(
        items=[_summary(row, limit=QUESTION_PREVIEW) for row in rows[:50]],
        limited=limited,
    )


def get_run(db: Session, user: User, run_id: UUID) -> AgentRunDetail:
    run = db.get(AgentRun, run_id)
    if run is None or run.user_id != user.id:
        raise api_error(404, "run_not_found")
    steps = runs_repo.list_steps_for_run(db, run.id)
    summary = _summary(run, limit=None)
    return AgentRunDetail(
        **summary.model_dump(),
        output=run.output,
        steps=[_step(step) for step in steps],
    )


def _summary(run: AgentRun, *, limit: int | None) -> AgentRunSummary:
    return AgentRunSummary(
        id=run.id,
        kind=run.kind,
        status=run.status,
        question=_question(run.input, limit=limit),
        prompt_tokens=run.prompt_tokens,
        completion_tokens=run.completion_tokens,
        duration_ms=run.duration_ms,
        created_at=run.created_at,
    )


def _step(step: AgentStep) -> AgentStepOut:
    return AgentStepOut(
        step_index=step.step_index,
        step_type=step.step_type,
        tool_name=step.tool_name,
        arguments=step.arguments,
        result_summary=step.result_summary,
        error=step.error,
        prompt_tokens=step.prompt_tokens,
        completion_tokens=step.completion_tokens,
        duration_ms=step.duration_ms,
    )


def _question(messages: object, *, limit: int | None) -> str:
    text = ""
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str):
                text = content
                break
    if limit is not None and len(text) > limit:
        return f"{text[:limit]}…"
    return text
