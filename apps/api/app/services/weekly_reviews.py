from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models.user import User
from app.providers import llm as llm_provider
from app.providers.prompts import (
    WEEKLY_REVIEW_SYSTEM_PROMPT,
    build_weekly_review_user_prompt,
)
from app.repositories import weekly_reviews as weekly_repo
from app.schemas.weekly_reviews import (
    GenerateWeeklyReviewRequest,
    SaveWeeklyReviewRequest,
    WeeklyReviewCitation,
    WeeklyReviewOut,
)
from app.services import weekly_review_sources


class _LlmWeeklyResult(BaseModel):
    status: Literal["ok", "insufficient_evidence"]
    completed: str = ""
    risks: str = ""
    recurring: str = ""
    next_week: str = ""
    citation_ids: list[str] = Field(default_factory=list)


def _empty_message(week_start: date, week_end: date) -> str:
    return (
        f"## 本周完成\n（暂无）\n\n"
        f"## 延期与风险\n（暂无）\n\n"
        f"## 重复问题\n（暂无）\n\n"
        f"## 下周重点\n（暂无）\n\n"
        f"本周（{week_start} – {week_end}）还没有足够的行动/复盘事实。"
        f"可以先发布复盘或推进几条行动后再生成。"
    )


def _assemble_markdown(result: _LlmWeeklyResult) -> str:
    return (
        f"## 本周完成\n{result.completed.strip() or '（暂无）'}\n\n"
        f"## 延期与风险\n{result.risks.strip() or '（暂无）'}\n\n"
        f"## 重复问题\n{result.recurring.strip() or '（暂无）'}\n\n"
        f"## 下周重点\n{result.next_week.strip() or '（暂无）'}\n"
    )


def get_saved(
    db: Session,
    user: User,
    week_start: date | None,
) -> WeeklyReviewOut:
    start, end = weekly_repo.resolve_week(week_start)
    row = weekly_repo.get_by_week(db, user_id=user.id, week_start=start)
    if row is None:
        return WeeklyReviewOut(
            week_start=start,
            week_end=end,
            status="empty",
            content_markdown="",
            citations=[],
            saved=False,
        )
    citations = [WeeklyReviewCitation.model_validate(c) for c in (row.citations or [])]
    return WeeklyReviewOut(
        week_start=row.week_start,
        week_end=row.week_end,
        status="ok",
        content_markdown=row.content_markdown,
        citations=citations,
        saved=True,
    )


def save(
    db: Session,
    user: User,
    week_start: date,
    payload: SaveWeeklyReviewRequest,
) -> WeeklyReviewOut:
    start, end = weekly_repo.resolve_week(week_start)
    citations = weekly_review_sources.resolve_citations(
        db,
        user_id=user.id,
        citation_ids=payload.citation_ids,
    )
    requested_ids = set(payload.citation_ids)
    if len(citations) != len(requested_ids):
        raise api_error(status.HTTP_400_BAD_REQUEST, "invalid_weekly_review_citations")
    row = weekly_repo.upsert(
        db,
        user_id=user.id,
        week_start=start,
        week_end=end,
        content_markdown=payload.content_markdown.strip(),
        citations=[citation.model_dump(mode="json") for citation in citations],
    )
    db.commit()
    db.refresh(row)
    return WeeklyReviewOut(
        week_start=row.week_start,
        week_end=row.week_end,
        status="ok",
        content_markdown=row.content_markdown,
        citations=[WeeklyReviewCitation.model_validate(c) for c in (row.citations or [])],
        saved=True,
    )


def generate(
    db: Session,
    user: User,
    payload: GenerateWeeklyReviewRequest,
) -> WeeklyReviewOut:
    start, end = weekly_repo.resolve_week(payload.week_start)
    today = datetime.now(UTC).date()

    verified = weekly_repo.list_verified_in_week(
        db, user_id=user.id, week_start=start, week_end=end
    )
    overdue = weekly_repo.list_overdue_active(db, user_id=user.id, today=today)
    awaiting = weekly_repo.list_awaiting_verify(db, user_id=user.id)
    due_soon = weekly_repo.list_due_this_week_active(
        db, user_id=user.id, week_start=start, week_end=end, today=today
    )
    rejected = weekly_repo.list_rejected_events_in_week(
        db, user_id=user.id, week_start=start, week_end=end
    )
    retros = weekly_repo.list_retros_in_week(
        db, user_id=user.id, week_start=start, week_end=end
    )
    clusters = weekly_repo.list_recurring_clusters_touched(
        db, user_id=user.id, week_start=start, week_end=end
    )

    fact_count = (
        len(verified)
        + len(overdue)
        + len(awaiting)
        + len(due_soon)
        + len(rejected)
        + len(retros)
        + len(clusters)
    )
    if fact_count == 0:
        return WeeklyReviewOut(
            week_start=start,
            week_end=end,
            status="empty",
            content_markdown=_empty_message(start, end),
            citations=[],
            saved=False,
        )

    catalog, context_blocks = weekly_review_sources.build_context(
        verified=verified,
        overdue=overdue,
        awaiting=awaiting,
        due_soon=due_soon,
        rejected=rejected,
        retros=retros,
        clusters=clusters,
    )

    messages = [
        {"role": "system", "content": WEEKLY_REVIEW_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_weekly_review_user_prompt(
                week_start=start.isoformat(),
                week_end=end.isoformat(),
                context_blocks=context_blocks,
            ),
        },
    ]

    try:
        raw = llm_provider.chat_json(messages)
        parsed = _LlmWeeklyResult.model_validate(json.loads(raw))
    except llm_provider.LlmError as exc:
        raise api_error(status.HTTP_502_BAD_GATEWAY, exc.message) from exc
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise api_error(status.HTTP_502_BAD_GATEWAY, "llm_bad_response") from exc

    if parsed.status == "insufficient_evidence":
        return WeeklyReviewOut(
            week_start=start,
            week_end=end,
            status="insufficient_evidence",
            content_markdown=_empty_message(start, end),
            citations=[],
            saved=False,
        )

    valid_ids = [cid for cid in parsed.citation_ids if cid in catalog][:8]
    if parsed.status == "ok" and not valid_ids:
        return WeeklyReviewOut(
            week_start=start,
            week_end=end,
            status="insufficient_evidence",
            content_markdown=_empty_message(start, end),
            citations=[],
            saved=False,
        )
    citations = [catalog[cid] for cid in valid_ids]
    return WeeklyReviewOut(
        week_start=start,
        week_end=end,
        status="ok",
        content_markdown=_assemble_markdown(parsed),
        citations=citations,
        saved=False,
    )
