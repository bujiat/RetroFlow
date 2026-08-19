from uuid import UUID

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import api_error
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories import users as users_repo

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise api_error(status.HTTP_401_UNAUTHORIZED, "not_authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(str(payload["sub"]))
    except (InvalidTokenError, KeyError, ValueError, TypeError):
        raise api_error(status.HTTP_401_UNAUTHORIZED, "invalid_token") from None

    user = users_repo.get_user_by_id(db, user_id)
    if user is None:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "invalid_token")

    return user
