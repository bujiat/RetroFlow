from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)


def create_user(
    db: Session,
    *,
    email: str,
    password_hash: str,
    locale: str,
) -> User:
    user = User(
        id=uuid4(),
        email=email,
        password_hash=password_hash,
        locale=locale,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
