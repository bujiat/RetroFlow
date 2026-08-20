from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.seed_demo import DEMO_EMAIL, DEMO_PASSWORD, ensure_demo_account


def test_demo_email_cannot_be_registered(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": DEMO_EMAIL, "password": "secret1", "locale": "zh-CN"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "email_already_registered"


def test_ensure_demo_account_can_login(client: TestClient, db_ready: None) -> None:
    db = SessionLocal()
    try:
        ensure_demo_account(db)
    finally:
        db.close()

    first = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert first.status_code == 200, first.text

    db = SessionLocal()
    try:
        ensure_demo_account(db)
    finally:
        db.close()

    again = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert again.status_code == 200, again.text
    assert again.json()["user"]["email"] == DEMO_EMAIL
