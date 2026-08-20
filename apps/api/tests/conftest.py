import os
from collections.abc import Callable, Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://retroflow:retroflow@localhost:5433/retroflow",
)

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.main import app
from app.models.user import User

AuthHeader = dict[str, str]
RegisterFn = Callable[[str], tuple[AuthHeader, dict]]


@pytest.fixture(autouse=True)
def disable_demo_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "seed_demo_on_start", False)


@pytest.fixture(autouse=True)
def test_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-key-for-jwt-validation-123")


@pytest.fixture(scope="session")
def db_ready() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL not running: {exc}")


@pytest.fixture
def client(db_ready: None) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def register_user(client: TestClient) -> Iterator[RegisterFn]:
    emails: list[str] = []

    def _register(prefix: str) -> tuple[AuthHeader, dict]:
        email = f"{prefix}-{uuid4().hex[:8]}@example.com"
        emails.append(email)
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "secret1", "locale": "en"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]

    yield _register

    db = SessionLocal()
    try:
        for email in emails:
            user = db.scalars(select(User).where(User.email == email)).first()
            if user is not None:
                db.delete(user)
        db.commit()
    finally:
        db.close()
