from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User


def load_user(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)
