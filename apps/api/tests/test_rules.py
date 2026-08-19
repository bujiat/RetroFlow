from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.actions import SubmitEvidenceRequest
from app.schemas.retros import PublishActionInput, PublishRetroRequest
from app.services import actions as actions_service
from app.services import retros as retros_service


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _action(**overrides: object) -> SimpleNamespace:
    today = datetime.now(UTC).date()
    item = SimpleNamespace(
        id=uuid4(),
        retro_id=uuid4(),
        problem_occurrence_id=uuid4(),
        title="发布脚本",
        description="d",
        owner="me",
        due_date=today,
        success_criteria="s",
        status="open",
        verified_at=None,
        created_at=datetime.now(UTC),
    )
    for key, value in overrides.items():
        setattr(item, key, value)
    return item


def test_my_week_buckets_by_status_and_due_date() -> None:
    today = datetime.now(UTC).date()
    week_end = today + timedelta(days=(6 - today.weekday()))
    rows = [
        _action(status="open", due_date=today - timedelta(days=1), title="overdue"),
        _action(status="open", due_date=today, title="this-week"),
        _action(
            status="open",
            due_date=week_end + timedelta(days=1),
            title="next-week",
        ),
        _action(status="evidence_submitted", due_date=today - timedelta(days=3), title="awaiting"),
        _action(status="verified", due_date=today - timedelta(days=1), title="done"),
    ]
    with patch(
        "app.services.actions.actions_repo.list_action_items_for_user",
        return_value=rows,
    ):
        week = actions_service.get_my_week(Mock(), _user())

    assert [item.title for item in week.overdue] == ["overdue"]
    assert [item.title for item in week.due_this_week] == ["this-week"]
    assert [item.title for item in week.awaiting_verify] == ["awaiting"]


def test_cannot_verify_without_evidence() -> None:
    item = _action(status="open")
    with patch("app.services.actions.actions_repo.get_action_for_user", return_value=item):
        with pytest.raises(HTTPException) as exc:
            actions_service.verify_action(Mock(), _user(), item.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == {"code": "invalid_status_transition"}


def test_cannot_submit_evidence_after_verified() -> None:
    item = _action(status="verified")
    payload = SubmitEvidenceRequest(completion_note="done", evidence_text="log")
    with patch("app.services.actions.actions_repo.get_action_for_user", return_value=item):
        with pytest.raises(HTTPException) as exc:
            actions_service.submit_evidence(Mock(), _user(), item.id, payload)
    assert exc.value.detail == {"code": "invalid_status_transition"}


def test_draft_retro_cannot_be_published() -> None:
    retro = SimpleNamespace(id=uuid4(), status="draft")
    payload = PublishRetroRequest(
        actions=[
            PublishActionInput(
                action_draft_id=uuid4(),
                owner="me",
                due_date=date(2026, 8, 20),
                success_criteria="shipped",
            )
        ]
    )
    with patch("app.services.retros.retros_repo.get_retro_for_user", return_value=retro):
        with pytest.raises(HTTPException) as exc:
            retros_service.publish_retro(Mock(), _user(), retro.id, payload)
    assert exc.value.detail == {"code": "retro_not_ready_to_publish"}


def test_publish_rejects_more_than_three_actions() -> None:
    action = PublishActionInput(
        action_draft_id=uuid4(),
        owner="me",
        due_date=date(2026, 8, 20),
        success_criteria="shipped",
    )
    with pytest.raises(ValidationError):
        PublishRetroRequest(actions=[action, action, action, action])


def test_evidence_requires_text_or_url() -> None:
    with pytest.raises(ValidationError):
        SubmitEvidenceRequest(completion_note="done")
