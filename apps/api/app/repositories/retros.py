from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.retro import Retro


def list_retros_for_user(db: Session, user_id: UUID) -> list[Retro]:
    stmt = (
        select(Retro)
        .where(Retro.user_id == user_id)
        .order_by(Retro.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_retro_for_user(
    db: Session,
    *,
    user_id: UUID,
    retro_id: UUID,
    for_update: bool = False,
) -> Retro | None:
    stmt = select(Retro).where(Retro.id == retro_id, Retro.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def create_retro(
    db: Session,
    *,
    user_id: UUID,
    type: str,
    title: str,
    review_date: date,
    raw_content: str,
) -> Retro:
    retro = Retro(
        id=uuid4(),
        user_id=user_id,
        type=type,
        title=title.strip(),
        review_date=review_date,
        raw_content=raw_content.strip(),
        status="draft",
        index_status="pending",
    )
    db.add(retro)
    db.commit()
    db.refresh(retro)
    return retro
