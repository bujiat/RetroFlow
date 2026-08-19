from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.repositories.weekly_reviews import resolve_week
from app.schemas.weekly_reviews import SaveWeeklyReviewRequest
from app.services.weekly_review_sources import resolve_citations


def test_resolve_week_normalizes_to_monday_and_sunday() -> None:
    start, end = resolve_week(date(2026, 8, 19))

    assert start == date(2026, 8, 17)
    assert end == date(2026, 8, 23)


def test_saved_review_requires_at_least_one_citation() -> None:
    with pytest.raises(ValidationError):
        SaveWeeklyReviewRequest(content_markdown="## 本周完成", citation_ids=[])


def test_resolve_citations_ignores_invalid_and_foreign_ids() -> None:
    user_id = uuid4()
    action_id = uuid4()

    with patch(
        "app.services.weekly_review_sources.weekly_repo.get_action_source",
        return_value=None,
    ) as get_action:
        citations = resolve_citations(
            Mock(),
            user_id=user_id,
            citation_ids=["not-an-id", f"action:{action_id}"],
        )

    assert citations == []
    get_action.assert_called_once()


def test_resolve_citations_rebuilds_action_snapshot_from_database() -> None:
    user_id = uuid4()
    action_id = uuid4()
    retro_id = uuid4()
    item = SimpleNamespace(
        id=action_id,
        retro_id=retro_id,
        title="固化发布脚本",
        status="in_progress",
        due_date=date(2026, 8, 20),
    )

    with patch(
        "app.services.weekly_review_sources.weekly_repo.get_action_source",
        return_value=item,
    ):
        citations = resolve_citations(
            Mock(),
            user_id=user_id,
            citation_ids=[f"action:{action_id}", f"action:{action_id}"],
        )

    assert len(citations) == 1
    assert citations[0].title == "固化发布脚本"
    assert citations[0].action_id == action_id
    assert citations[0].href_hint == "/actions/board"
