from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep

LIST_FETCH = 51


def list_runs_statement(user_id: UUID):
    return (
        select(AgentRun)
        .where(AgentRun.user_id == user_id)
        .order_by(AgentRun.created_at.desc())
        .limit(LIST_FETCH)
    )


def list_steps_statement(run_id: UUID):
    return (
        select(AgentStep)
        .where(AgentStep.run_id == run_id)
        .order_by(AgentStep.step_index.asc())
    )


def list_runs_for_user(db: Session, user_id: UUID) -> list[AgentRun]:
    return list(db.scalars(list_runs_statement(user_id)).all())


def list_steps_for_run(db: Session, run_id: UUID) -> list[AgentStep]:
    return list(db.scalars(list_steps_statement(run_id)).all())
