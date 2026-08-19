from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.security import decode_access_token


def test_expired_jwt_does_not_decode() -> None:
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "email": "old@test.local",
            "exp": datetime.now(UTC) - timedelta(seconds=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_production_rejects_development_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://example",
            jwt_secret="dev-change-me",
            cors_origins="https://retroflow.example.com",
        )


def test_production_accepts_public_origins_and_strong_secret() -> None:
    config = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+psycopg://example",
        jwt_secret="production-secret-at-least-32-characters",
        cors_origins="https://retroflow.example.com",
    )
    assert config.cors_origin_list == ["https://retroflow.example.com"]


def test_duplicate_email_is_rejected(client: TestClient, register_user) -> None:
    headers, user = register_user("dup")
    again = client.post(
        "/api/v1/auth/register",
        json={"email": user["email"], "password": "secret1", "locale": "en"},
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "email_already_registered"
    assert headers["Authorization"].startswith("Bearer ")


def test_wrong_password_is_rejected(client: TestClient, register_user) -> None:
    _, user = register_user("login")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "wrong12"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "incorrect_password"


def test_missing_token_is_unauthorized(client: TestClient) -> None:
    response = client.get("/api/v1/retros")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"
