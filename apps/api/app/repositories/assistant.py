from collections.abc import Collection
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action_item import ActionItem
from app.models.problem import ProblemOccurrence
from app.models.problem_cluster import ProblemCluster
from app.models.retro import Retro


def retros_by_ids(
    db: Session,
    *,
    user_id: UUID,
    retro_ids: Collection[UUID],
) -> dict[UUID, Retro]:
    rows = db.scalars(
        select(Retro).where(Retro.user_id == user_id, Retro.id.in_(retro_ids))
    ).all()
    return {row.id: row for row in rows}


def list_problems(
    db: Session,
    *,
    user_id: UUID,
    retro_ids: Collection[UUID],
    limit: int = 5,
) -> list[ProblemOccurrence]:
    return list(
        db.scalars(
            select(ProblemOccurrence)
            .where(
                ProblemOccurrence.user_id == user_id,
                ProblemOccurrence.retro_id.in_(retro_ids),
                ProblemOccurrence.disposition == "kept",
            )
            .order_by(ProblemOccurrence.created_at.desc())
            .limit(limit)
        ).all()
    )


def list_actions(
    db: Session,
    *,
    user_id: UUID,
    retro_ids: Collection[UUID],
    limit: int = 5,
) -> list[ActionItem]:
    return list(
        db.scalars(
            select(ActionItem)
            .where(
                ActionItem.user_id == user_id,
                ActionItem.retro_id.in_(retro_ids),
                ActionItem.status != "cancelled",
            )
            .order_by(ActionItem.updated_at.desc())
            .limit(limit)
        ).all()
    )


def clusters_by_ids(
    db: Session,
    *,
    user_id: UUID,
    cluster_ids: Collection[UUID],
) -> dict[UUID, ProblemCluster]:
    rows = db.scalars(
        select(ProblemCluster).where(
            ProblemCluster.user_id == user_id,
            ProblemCluster.id.in_(cluster_ids),
        )
    ).all()
    return {row.id: row for row in rows}
