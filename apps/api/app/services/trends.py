from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.action_item import ActionItem
from app.models.problem import ProblemOccurrence
from app.models.problem_cluster import ProblemCluster
from app.models.retro import Retro
from app.models.user import User
from app.schemas.trends import ClusterTrendBrief, OverdueActionBrief, TrendsSummary

_ACTIVE = ("open", "in_progress", "evidence_submitted")


def get_summary(db: Session, user: User) -> TrendsSummary:
    user_id = user.id
    today = datetime.now(UTC).date()

    counts = dict(
        db.execute(
            select(ActionItem.status, func.count())
            .where(ActionItem.user_id == user_id)
            .group_by(ActionItem.status)
        ).all()
    )

    open_n = counts.get("open", 0)
    progress_n = counts.get("in_progress", 0)
    evidence_n = counts.get("evidence_submitted", 0)
    verified_n = counts.get("verified", 0)
    cancelled_n = counts.get("cancelled", 0)

    awaiting_work = open_n + progress_n
    denom = verified_n + awaiting_work + evidence_n
    rate = round(verified_n / denom, 4) if denom else None

    overdue_n = db.scalar(
        select(func.count())
        .select_from(ActionItem)
        .where(
            ActionItem.user_id == user_id,
            ActionItem.status.in_(_ACTIVE),
            ActionItem.due_date < today,
        )
    ) or 0

    overdue_rows = db.scalars(
        select(ActionItem)
        .where(
            ActionItem.user_id == user_id,
            ActionItem.status.in_(_ACTIVE),
            ActionItem.due_date < today,
        )
        .order_by(ActionItem.due_date.asc())
        .limit(10)
    ).all()

    kept_problems = db.scalar(
        select(func.count())
        .select_from(ProblemOccurrence)
        .where(
            ProblemOccurrence.user_id == user_id,
            ProblemOccurrence.disposition == "kept",
        )
    ) or 0

    published_retros = db.scalar(
        select(func.count())
        .select_from(Retro)
        .where(Retro.user_id == user_id, Retro.status == "published")
    ) or 0

    cluster_rows = db.execute(
        select(ProblemCluster, func.count(ProblemOccurrence.id))
        .join(
            ProblemOccurrence,
            (ProblemOccurrence.cluster_id == ProblemCluster.id)
            & (ProblemOccurrence.disposition == "kept"),
        )
        .where(ProblemCluster.user_id == user_id)
        .group_by(ProblemCluster.id)
        .order_by(func.count(ProblemOccurrence.id).desc())
        .limit(8)
    ).all()

    top_clusters = [
        ClusterTrendBrief(
            id=cluster.id,
            title=cluster.canonical_title,
            occurrence_count=count,
        )
        for cluster, count in cluster_rows
    ]

    recurring_subq = (
        select(ProblemCluster.id)
        .join(
            ProblemOccurrence,
            (ProblemOccurrence.cluster_id == ProblemCluster.id)
            & (ProblemOccurrence.disposition == "kept"),
        )
        .where(ProblemCluster.user_id == user_id)
        .group_by(ProblemCluster.id)
        .having(func.count(ProblemOccurrence.id) >= 2)
        .subquery()
    )
    recurring_clusters = db.scalar(select(func.count()).select_from(recurring_subq)) or 0

    return TrendsSummary(
        overdue_actions=overdue_n,
        awaiting_work=awaiting_work,
        awaiting_verify=evidence_n,
        verified_actions=verified_n,
        cancelled_actions=cancelled_n,
        verification_rate=rate,
        kept_problems=kept_problems,
        published_retros=published_retros,
        recurring_clusters=recurring_clusters,
        top_clusters=top_clusters,
        overdue_items=[
            OverdueActionBrief(
                id=row.id,
                title=row.title,
                owner=row.owner,
                due_date=row.due_date,
                status=row.status,
            )
            for row in overdue_rows
        ],
    )
