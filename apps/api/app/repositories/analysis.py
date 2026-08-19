from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.action_draft import ActionDraft
from app.models.problem import ProblemOccurrence
from app.schemas.analysis import LlmAnalysisResult


def list_problems_for_retro(
    db: Session,
    *,
    user_id: UUID,
    retro_id: UUID,
) -> list[ProblemOccurrence]:
    stmt = (
        select(ProblemOccurrence)
        .where(
            ProblemOccurrence.user_id == user_id,
            ProblemOccurrence.retro_id == retro_id,
        )
        .order_by(ProblemOccurrence.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def list_action_drafts_for_retro(
    db: Session,
    *,
    user_id: UUID,
    retro_id: UUID,
) -> list[ActionDraft]:
    stmt = (
        select(ActionDraft)
        .where(ActionDraft.user_id == user_id, ActionDraft.retro_id == retro_id)
        .order_by(ActionDraft.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def replace_analysis_results(
    db: Session,
    *,
    user_id: UUID,
    retro_id: UUID,
    analysis: LlmAnalysisResult,
) -> tuple[list[ProblemOccurrence], list[ActionDraft]]:
    db.execute(
        delete(ActionDraft).where(
            ActionDraft.user_id == user_id,
            ActionDraft.retro_id == retro_id,
        )
    )
    db.execute(
        delete(ProblemOccurrence).where(
            ProblemOccurrence.user_id == user_id,
            ProblemOccurrence.retro_id == retro_id,
        )
    )
    db.flush()

    problems: list[ProblemOccurrence] = []
    drafts: list[ActionDraft] = []

    for item in analysis.problems:
        problem = ProblemOccurrence(
            id=uuid4(),
            user_id=user_id,
            retro_id=retro_id,
            title=item.title,
            normalized_statement=item.normalized_statement,
            category=item.category,
            severity=item.severity,
            source_quote=item.source_quote,
            disposition="kept",
            match_status="pending",
        )
        db.add(problem)
        problems.append(problem)
        db.flush()

        for action in item.suggested_actions:
            draft = ActionDraft(
                id=uuid4(),
                user_id=user_id,
                retro_id=retro_id,
                problem_occurrence_id=problem.id,
                title=action.title,
                description=action.description,
                suggested_success_criteria=action.suggested_success_criteria,
            )
            db.add(draft)
            drafts.append(draft)

    return problems, drafts
