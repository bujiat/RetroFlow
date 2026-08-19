from uuid import UUID

from fastapi import status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models.problem import ProblemOccurrence
from app.models.user import User
from app.repositories import clusters as clusters_repo


class ProblemClusterOut(BaseModel):
    id: UUID
    canonical_title: str
    category: str
    occurrence_count: int = 0

    model_config = {"from_attributes": True}


class RelinkOccurrenceRequest(BaseModel):
    cluster_id: UUID | None = None
    new_cluster_title: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def one_target(self) -> "RelinkOccurrenceRequest":
        has_id = self.cluster_id is not None
        title = (self.new_cluster_title or "").strip()
        has_new = bool(title)
        if has_id == has_new:
            raise ValueError("provide exactly one of cluster_id or new_cluster_title")
        if has_new:
            self.new_cluster_title = title
        return self


def list_clusters(db: Session, user: User) -> list[ProblemClusterOut]:
    rows = clusters_repo.list_clusters_for_user(db, user.id)
    return [
        ProblemClusterOut(
            id=cluster.id,
            canonical_title=cluster.canonical_title,
            category=cluster.category,
            occurrence_count=count,
        )
        for cluster, count in rows
    ]


def relink_occurrence(
    db: Session,
    user: User,
    occurrence_id: UUID,
    payload: RelinkOccurrenceRequest,
) -> ProblemClusterOut:
    problem = clusters_repo.get_occurrence_for_user(
        db,
        user_id=user.id,
        occurrence_id=occurrence_id,
    )
    if problem is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "occurrence_not_found")

    if payload.cluster_id is not None:
        cluster = clusters_repo.get_cluster_for_user(
            db,
            user_id=user.id,
            cluster_id=payload.cluster_id,
        )
        if cluster is None:
            raise api_error(status.HTTP_404_NOT_FOUND, "cluster_not_found")
    else:
        cluster = clusters_repo.create_cluster(
            db,
            user_id=user.id,
            title=payload.new_cluster_title or problem.title,
            category=problem.category,
        )

    problem.cluster_id = cluster.id
    problem.match_status = "manual"
    db.commit()
    count = (
        db.scalar(
            select(func.count())
            .select_from(ProblemOccurrence)
            .where(
                ProblemOccurrence.user_id == user.id,
                ProblemOccurrence.cluster_id == cluster.id,
                ProblemOccurrence.disposition == "kept",
            )
        )
        or 0
    )
    return ProblemClusterOut(
        id=cluster.id,
        canonical_title=cluster.canonical_title,
        category=cluster.category,
        occurrence_count=count,
    )
