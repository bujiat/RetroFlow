from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action_draft import ActionDraft
from app.models.action_event import ActionEvent
from app.models.action_item import ActionItem
from app.models.problem import ProblemOccurrence
from app.schemas.retros import PublishActionInput


def get_drafts_by_ids(
    db: Session,
    *,
    user_id: UUID,
    retro_id: UUID,
    draft_ids: list[UUID],
) -> list[ActionDraft]:
    if not draft_ids:
        return []
    stmt = select(ActionDraft).where(
        ActionDraft.user_id == user_id,
        ActionDraft.retro_id == retro_id,
        ActionDraft.id.in_(draft_ids),
    )
    return list(db.scalars(stmt).all())


def mark_problems_discarded(db: Session, problems: list[ProblemOccurrence]) -> None:
    for problem in problems:
        problem.disposition = "discarded"


def create_action_items_from_drafts(
    db: Session,
    *,
    user_id: UUID,
    retro_id: UUID,
    drafts_by_id: dict[UUID, ActionDraft],
    actions: list[PublishActionInput],
) -> list[ActionItem]:
    created: list[ActionItem] = []
    for action in actions:
        draft = drafts_by_id[action.action_draft_id]
        item = ActionItem(
            id=uuid4(),
            user_id=user_id,
            retro_id=retro_id,
            problem_occurrence_id=draft.problem_occurrence_id,
            title=draft.title,
            description=draft.description,
            owner=action.owner,
            due_date=action.due_date,
            success_criteria=action.success_criteria,
            status="open",
        )
        db.add(item)
        # 先把 action_items 刷进库，再插事件；否则 UoW 可能先插 events 触发 FK 失败
        db.flush()
        db.add(
            ActionEvent(
                id=uuid4(),
                user_id=user_id,
                action_id=item.id,
                event_type="created",
                from_status=None,
                to_status="open",
                note=None,
                evidence_text=None,
                evidence_url=None,
            )
        )
        created.append(item)
    return created


def list_action_items_for_user(db: Session, user_id: UUID) -> list[ActionItem]:
    stmt = (
        select(ActionItem)
        .where(ActionItem.user_id == user_id)
        .order_by(ActionItem.due_date.asc(), ActionItem.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_action_for_user(
    db: Session,
    *,
    user_id: UUID,
    action_id: UUID,
) -> ActionItem | None:
    stmt = select(ActionItem).where(
        ActionItem.user_id == user_id,
        ActionItem.id == action_id,
    )
    return db.scalars(stmt).first()


def list_events_for_action(
    db: Session,
    *,
    user_id: UUID,
    action_id: UUID,
) -> list[ActionEvent]:
    stmt = (
        select(ActionEvent)
        .where(
            ActionEvent.user_id == user_id,
            ActionEvent.action_id == action_id,
        )
        .order_by(ActionEvent.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def add_event(
    db: Session,
    *,
    user_id: UUID,
    action_id: UUID,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    note: str | None = None,
    evidence_text: str | None = None,
    evidence_url: str | None = None,
) -> ActionEvent:
    event = ActionEvent(
        id=uuid4(),
        user_id=user_id,
        action_id=action_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        note=note,
        evidence_text=evidence_text,
        evidence_url=evidence_url,
    )
    db.add(event)
    return event
