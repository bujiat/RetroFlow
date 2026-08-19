from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories import users as users_repo
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserPublic


def register_user(db: Session, payload: RegisterRequest) -> AuthResponse:
    email = payload.email.lower().strip()
    existing = users_repo.get_user_by_email(db, email)
    if existing is not None:
        raise api_error(status.HTTP_409_CONFLICT, "email_already_registered")

    try:
        user = users_repo.create_user(
            db,
            email=email,
            password_hash=hash_password(payload.password),
            locale=payload.locale,
        )
    except IntegrityError as exc:
        db.rollback()
        raise api_error(status.HTTP_409_CONFLICT, "email_already_registered") from exc
    token = create_access_token(user_id=user.id, email=user.email)
    return AuthResponse(
        access_token=token,
        user=UserPublic.model_validate(user),
    )


def login_user(db: Session, payload: LoginRequest) -> AuthResponse:
    email = payload.email.lower().strip()
    user = users_repo.get_user_by_email(db, email)
    if user is None:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "email_not_registered")
    if not verify_password(payload.password, user.password_hash):
        raise api_error(status.HTTP_401_UNAUTHORIZED, "incorrect_password")

    token = create_access_token(user_id=user.id, email=user.email)
    return AuthResponse(
        access_token=token,
        user=UserPublic.model_validate(user),
    )
