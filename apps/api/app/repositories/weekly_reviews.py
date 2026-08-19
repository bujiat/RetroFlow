from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.action_event import ActionEvent
from app.models.action_item import ActionItem
from app.models.problem import ProblemOccurrence
from app.models.problem_cluster import ProblemCluster
from app.models.retro import Retro
from app.models.weekly_review import WeeklyReview


def resolve_week(week_start: date | None) -> tuple[date, date]:
    """ISO-style week: Monday … Sunday."""
    today = datetime.now(UTC).date()
    start = week_start if week_start is not None else today
    start = start - timedelta(days=start.weekday())
    end = start + timedelta(days=6)
    return start, end


def week_utc_range(week_start: date, week_end: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=UTC)
    end_exclusive = datetime.combine(
        week_end + timedelta(days=1),
        datetime.min.time(),
        tzinfo=UTC,
    )
    return start_dt, end_exclusive


def get_by_week(
    db: Session,
    *,
    user_id: UUID,
    week_start: date,
) -> WeeklyReview | None:
    stmt = select(WeeklyReview).where(
        WeeklyReview.user_id == user_id,
        WeeklyReview.week_start == week_start,
    )
    return db.scalars(stmt).first()


def upsert(
    db: Session,
    *,
    user_id: UUID,
    week_start: date,
    week_end: date,
    content_markdown: str,
    citations: list[dict],
) -> WeeklyReview:
    row = get_by_week(db, user_id=user_id, week_start=week_start)
    if row is None:
        row = WeeklyReview(
            id=uuid4(),
            user_id=user_id,
            week_start=week_start,
            week_end=week_end,
            content_markdown=content_markdown,
            citations=citations,
        )
        db.add(row)
    else:
        row.week_end = week_end
        row.content_markdown = content_markdown
        row.citations = citations
    db.flush()
    return row


def list_verified_in_week(
    db: Session,
    *,
    user_id: UUID,
    week_start: date,
    week_end: date,
) -> list[ActionItem]:
    start_dt, end_dt = week_utc_range(week_start, week_end)
    stmt = (
        select(ActionItem)
        .where(
            ActionItem.user_id == user_id,
            ActionItem.status == "verified",
            ActionItem.verified_at.is_not(None),
            ActionItem.verified_at >= start_dt,
            ActionItem.verified_at < end_dt,
        )
        .order_by(ActionItem.verified_at.desc())
        .limit(20)
    )
    return list(db.scalars(stmt).all())


def list_overdue_active(
    db: Session,
    *,
    user_id: UUID,
    today: date,
) -> list[ActionItem]:
    stmt = (
        select(ActionItem)
        .where(
            ActionItem.user_id == user_id,
            ActionItem.status.in_(("open", "in_progress")),
            ActionItem.due_date < today,
        )
        .order_by(ActionItem.due_date.asc())
        .limit(20)
    )
    return list(db.scalars(stmt).all())


def list_awaiting_verify(db: Session, *, user_id: UUID) -> list[ActionItem]:
    stmt = (
        select(ActionItem)
        .where(
            ActionItem.user_id == user_id,
            ActionItem.status == "evidence_submitted",
        )
        .order_by(ActionItem.due_date.asc())
        .limit(20)
    )
    return list(db.scalars(stmt).all())


def list_due_this_week_active(
    db: Session,
    *,
    user_id: UUID,
    week_start: date,
    week_end: date,
    today: date,
) -> list[ActionItem]:
    stmt = (
        select(ActionItem)
        .where(
            ActionItem.user_id == user_id,
            ActionItem.status.in_(("open", "in_progress")),
            ActionItem.due_date >= today,
            ActionItem.due_date >= week_start,
            ActionItem.due_date <= week_end,
        )
        .order_by(ActionItem.due_date.asc())
        .limit(20)
    )
    return list(db.scalars(stmt).all())


def list_rejected_events_in_week(
    db: Session,
    *,
    user_id: UUID,
    week_start: date,
    week_end: date,
) -> list[tuple[ActionEvent, ActionItem]]:
    start_dt, end_dt = week_utc_range(week_start, week_end)
    stmt = (
        select(ActionEvent, ActionItem)
        .join(ActionItem, ActionItem.id == ActionEvent.action_id)
        .where(
            ActionEvent.user_id == user_id,
            ActionItem.user_id == user_id,
            ActionEvent.event_type == "rejected",
            ActionEvent.created_at >= start_dt,
            ActionEvent.created_at < end_dt,
        )
        .order_by(ActionEvent.created_at.desc())
        .limit(20)
    )
    return list(db.execute(stmt).all())


def list_retros_in_week(
    db: Session,
    *,
    user_id: UUID,
    week_start: date,
    week_end: date,
) -> list[Retro]:
    stmt = (
        select(Retro)
        .where(
            Retro.user_id == user_id,
            Retro.review_date >= week_start,
            Retro.review_date <= week_end,
            Retro.status.in_(("ready_for_review", "published")),
        )
        .order_by(Retro.review_date.desc())
        .limit(10)
    )
    return list(db.scalars(stmt).all())


def list_recurring_clusters_touched(
    db: Session,
    *,
    user_id: UUID,
    week_start: date,
    week_end: date,
) -> list[tuple[ProblemCluster, int]]:
    """Clusters with a kept occurrence this week and total kept count >= 2."""
    week_cluster_ids = (
        select(ProblemOccurrence.cluster_id)
        .join(Retro, Retro.id == ProblemOccurrence.retro_id)
        .where(
            ProblemOccurrence.user_id == user_id,
            Retro.user_id == user_id,
            Retro.review_date >= week_start,
            Retro.review_date <= week_end,
            ProblemOccurrence.disposition == "kept",
            ProblemOccurrence.cluster_id.is_not(None),
        )
        .distinct()
    )

    total_counts = (
        select(
            ProblemOccurrence.cluster_id.label("cluster_id"),
            func.count(ProblemOccurrence.id).label("cnt"),
        )
        .where(
            ProblemOccurrence.user_id == user_id,
            ProblemOccurrence.disposition == "kept",
            ProblemOccurrence.cluster_id.is_not(None),
        )
        .group_by(ProblemOccurrence.cluster_id)
        .subquery()
    )

    stmt = (
        select(ProblemCluster, total_counts.c.cnt)
        .join(total_counts, total_counts.c.cluster_id == ProblemCluster.id)
        .where(
            ProblemCluster.user_id == user_id,
            ProblemCluster.id.in_(week_cluster_ids),
            total_counts.c.cnt >= 2,
        )
        .order_by(total_counts.c.cnt.desc())
        .limit(10)
    )
    return list(db.execute(stmt).all())


def get_action_source(
    db: Session,
    *,
    user_id: UUID,
    action_id: UUID,
) -> ActionItem | None:
    return db.scalars(
        select(ActionItem).where(
            ActionItem.user_id == user_id,
            ActionItem.id == action_id,
        )
    ).first()


def get_event_source(
    db: Session,
    *,
    user_id: UUID,
    event_id: UUID,
) -> tuple[ActionEvent, ActionItem] | None:
    return db.execute(
        select(ActionEvent, ActionItem)
        .join(ActionItem, ActionItem.id == ActionEvent.action_id)
        .where(
            ActionEvent.user_id == user_id,
            ActionEvent.id == event_id,
            ActionItem.user_id == user_id,
        )
    ).first()


def get_retro_source(
    db: Session,
    *,
    user_id: UUID,
    retro_id: UUID,
) -> Retro | None:
    return db.scalars(
        select(Retro).where(
            Retro.user_id == user_id,
            Retro.id == retro_id,
        )
    ).first()


def get_cluster_source(
    db: Session,
    *,
    user_id: UUID,
    cluster_id: UUID,
) -> ProblemCluster | None:
    return db.scalars(
        select(ProblemCluster).where(
            ProblemCluster.user_id == user_id,
            ProblemCluster.id == cluster_id,
        )
    ).first()
