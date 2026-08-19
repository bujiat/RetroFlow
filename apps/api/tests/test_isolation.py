from datetime import date
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models.action_item import ActionItem
from app.models.problem import ProblemOccurrence


def test_cross_user_404(client: TestClient, register_user) -> None:
    headers_a, user_a = register_user("owner")
    headers_b, _ = register_user("other")

    created = client.post(
        "/api/v1/retros",
        headers=headers_a,
        json={
            "type": "sprint",
            "title": "owner retro",
            "review_date": date(2026, 8, 17).isoformat(),
            "raw_content": "keep this private",
        },
    )
    assert created.status_code == 201, created.text
    retro_id = created.json()["id"]

    stolen = client.get(f"/api/v1/retros/{retro_id}", headers=headers_b)
    assert stolen.status_code == 404
    assert stolen.json()["detail"]["code"] == "retro_not_found"
    assert client.get("/api/v1/retros", headers=headers_b).json() == []

    problem_id = uuid4()
    action_id = uuid4()
    with SessionLocal() as db:
        db.add(
            ProblemOccurrence(
                id=problem_id,
                user_id=UUID(user_a["id"]),
                retro_id=UUID(retro_id),
                title="private problem",
                normalized_statement="private problem",
                category="delivery",
                severity="high",
                source_quote="private",
                disposition="kept",
                match_status="pending",
            )
        )
        db.flush()
        db.add(
            ActionItem(
                id=action_id,
                user_id=UUID(user_a["id"]),
                retro_id=UUID(retro_id),
                problem_occurrence_id=problem_id,
                title="private action",
                description="private",
                owner="owner",
                due_date=date(2026, 8, 20),
                success_criteria="private",
                status="open",
            )
        )
        db.commit()

    blocked = client.patch(
        f"/api/v1/actions/{action_id}",
        headers=headers_b,
        json={"status": "in_progress"},
    )
    assert blocked.status_code == 404
    assert blocked.json()["detail"]["code"] == "action_not_found"
