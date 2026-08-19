from uuid import UUID

from sqlalchemy.orm import Session

from app.models.action_event import ActionEvent
from app.models.action_item import ActionItem
from app.models.problem_cluster import ProblemCluster
from app.models.retro import Retro
from app.repositories import weekly_reviews as weekly_repo
from app.schemas.weekly_reviews import WeeklyReviewCitation


def _add_action(
    catalog: dict[str, WeeklyReviewCitation],
    lines: list[str],
    *,
    item: ActionItem,
    bucket: str,
    excerpt: str,
    line_extra: str = "",
) -> None:
    cid = f"action:{item.id}"
    catalog[cid] = WeeklyReviewCitation(
        id=cid,
        source_type="action",
        title=item.title,
        excerpt=excerpt,
        retro_id=item.retro_id,
        action_id=item.id,
        href_hint="/actions/board",
    )
    extra = f" {line_extra}" if line_extra else ""
    lines.append(f"[{cid}] type=action bucket={bucket} title={item.title}{extra}")


def build_context(
    *,
    verified: list[ActionItem],
    overdue: list[ActionItem],
    awaiting: list[ActionItem],
    due_soon: list[ActionItem],
    rejected: list[tuple[ActionEvent, ActionItem]],
    retros: list[Retro],
    clusters: list[tuple[ProblemCluster, int]],
) -> tuple[dict[str, WeeklyReviewCitation], str]:
    """Convert database facts into LLM context plus a citation allowlist."""
    catalog: dict[str, WeeklyReviewCitation] = {}
    lines: list[str] = []

    action_groups = (
        (
            verified,
            "verified",
            lambda item: f"verified · due {item.due_date}",
            lambda item: f"owner={item.owner}",
        ),
        (
            overdue,
            "overdue",
            lambda item: f"{item.status} · overdue since {item.due_date}",
            lambda item: f"status={item.status} due={item.due_date}",
        ),
        (
            awaiting,
            "awaiting_verify",
            lambda item: f"awaiting verify · due {item.due_date}",
            lambda item: f"due={item.due_date}",
        ),
        (
            due_soon,
            "due_this_week",
            lambda item: f"{item.status} · due {item.due_date}",
            lambda item: f"status={item.status} due={item.due_date}",
        ),
    )
    for items, bucket, excerpt_for, extra_for in action_groups:
        for item in items:
            _add_action(
                catalog,
                lines,
                item=item,
                bucket=bucket,
                excerpt=excerpt_for(item),
                line_extra=extra_for(item),
            )

    for event, item in rejected:
        cid = f"event:{event.id}"
        catalog[cid] = WeeklyReviewCitation(
            id=cid,
            source_type="event",
            title=f"退回：{item.title}",
            excerpt=(event.note or "")[:280] or "rejected",
            retro_id=item.retro_id,
            action_id=item.id,
            href_hint="/actions/board",
        )
        lines.append(
            f"[{cid}] type=event bucket=rejected action={item.title} note={event.note or '-'}"
        )

    for retro in retros:
        cid = f"retro:{retro.id}"
        catalog[cid] = WeeklyReviewCitation(
            id=cid,
            source_type="retro",
            title=retro.title,
            excerpt=f"review_date={retro.review_date} status={retro.status}",
            retro_id=retro.id,
            href_hint=f"/retro/{retro.id}/confirm",
        )
        lines.append(
            f"[{cid}] type=retro title={retro.title} date={retro.review_date} status={retro.status}"
        )

    for cluster, count in clusters:
        cid = f"cluster:{cluster.id}"
        catalog[cid] = WeeklyReviewCitation(
            id=cid,
            source_type="cluster",
            title=cluster.canonical_title,
            excerpt=f"出现 {count} 次（本周有新出现）",
            href_hint="/trends",
        )
        lines.append(
            f"[{cid}] type=cluster title={cluster.canonical_title} total_occurrences={count}"
        )

    return catalog, "\n\n".join(lines)


def resolve_citations(
    db: Session,
    *,
    user_id: UUID,
    citation_ids: list[str],
) -> list[WeeklyReviewCitation]:
    """Rebuild citation snapshots from user-owned rows; never trust client metadata."""
    citations: list[WeeklyReviewCitation] = []
    seen: set[str] = set()

    for citation_id in citation_ids:
        if citation_id in seen:
            continue
        seen.add(citation_id)

        try:
            source_type, raw_id = citation_id.split(":", maxsplit=1)
            source_id = UUID(raw_id)
        except (ValueError, TypeError):
            continue

        citation: WeeklyReviewCitation | None = None
        if source_type == "action":
            item = weekly_repo.get_action_source(
                db, user_id=user_id, action_id=source_id
            )
            if item is not None:
                citation = WeeklyReviewCitation(
                    id=citation_id,
                    source_type="action",
                    title=item.title,
                    excerpt=f"{item.status} · due {item.due_date}",
                    retro_id=item.retro_id,
                    action_id=item.id,
                    href_hint="/actions/board",
                )
        elif source_type == "event":
            row = weekly_repo.get_event_source(db, user_id=user_id, event_id=source_id)
            if row is not None:
                event, item = row
                citation = WeeklyReviewCitation(
                    id=citation_id,
                    source_type="event",
                    title=f"{event.event_type}：{item.title}",
                    excerpt=(event.note or event.evidence_text or event.event_type)[:280],
                    retro_id=item.retro_id,
                    action_id=item.id,
                    href_hint="/actions/board",
                )
        elif source_type == "retro":
            retro = weekly_repo.get_retro_source(
                db, user_id=user_id, retro_id=source_id
            )
            if retro is not None:
                citation = WeeklyReviewCitation(
                    id=citation_id,
                    source_type="retro",
                    title=retro.title,
                    excerpt=f"review_date={retro.review_date} status={retro.status}",
                    retro_id=retro.id,
                    href_hint=f"/retro/{retro.id}/confirm",
                )
        elif source_type == "cluster":
            cluster = weekly_repo.get_cluster_source(
                db, user_id=user_id, cluster_id=source_id
            )
            if cluster is not None:
                citation = WeeklyReviewCitation(
                    id=citation_id,
                    source_type="cluster",
                    title=cluster.canonical_title,
                    excerpt=cluster.canonical_title,
                    href_hint="/trends",
                )

        if citation is not None:
            citations.append(citation)

    return citations
