import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.agent.tools import actions as actions_module
from app.agent.tools import problems as problems_module
from app.agent.tools.executor import execute_tool
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.action_event import ActionEvent
from app.models.action_item import ActionItem
from app.models.problem import ProblemOccurrence
from app.models.problem_cluster import ProblemCluster
from app.models.retro import Retro
from app.models.user import User
from app.schemas.actions import ActionItemOut


def test_weak_similarity_is_not_a_match(monkeypatch: pytest.MonkeyPatch) -> None:
    cluster = SimpleNamespace(
        id=uuid4(),
        canonical_title="部署失败",
        category="delivery",
    )
    monkeypatch.setattr(
        problems_module.embedding_provider,
        "embed_texts",
        lambda _texts: [[0.1] * settings.embedding_dim],
    )
    monkeypatch.setattr(
        problems_module.clusters_repo,
        "find_nearest_cluster",
        lambda *args, **kwargs: (cluster, settings.problem_match_threshold - 0.01),
    )
    result = execute_tool(
        _unused_db(),
        user_id=uuid4(),
        name="find_similar_problems",
        arguments={"query": "部署失败"},
    )
    assert result["ok"] is True
    assert result["data"]["match"] is None


def test_list_all_keeps_open_items_ahead_of_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    cancelled = _fake_action("old cancelled", "cancelled", date(2020, 1, 1))
    current = _fake_action("current open", "open", date(2026, 12, 1))
    monkeypatch.setattr(actions_module, "load_user", lambda db, user_id: SimpleNamespace(id=user_id))
    monkeypatch.setattr(
        actions_module.actions_service,
        "list_actions",
        lambda db, user: [cancelled, current],
    )
    result = execute_tool(
        _unused_db(),
        user_id=user_id,
        name="list_actions",
        arguments={"focus": "all"},
    )
    titles = [item["title"] for item in result["data"]["items"]]
    assert titles == ["current open", "old cancelled"]


def test_list_actions_rejects_unknown_focus() -> None:
    result = execute_tool(
        _unused_db(),
        user_id=uuid4(),
        name="list_actions",
        arguments={"focus": "everyone"},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_action_history_rejects_bad_id() -> None:
    result = execute_tool(
        _unused_db(),
        user_id=uuid4(),
        name="get_action_history",
        arguments={"action_id": "action:not-a-uuid"},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_trends_rejects_user_id() -> None:
    result = execute_tool(
        _unused_db(),
        user_id=uuid4(),
        name="get_trends",
        arguments={"user_id": str(uuid4())},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_find_similar_problems_hides_other_users(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_postgres()
    vector = [1.0] + [0.0] * (settings.embedding_dim - 1)
    monkeypatch.setattr(
        problems_module.embedding_provider,
        "embed_texts",
        lambda _texts: [vector],
    )
    db = SessionLocal()
    pair = _seed(db)
    try:
        hidden = execute_tool(
            db,
            user_id=pair.user_a,
            name="find_similar_problems",
            arguments={"query": "部署失败"},
        )
        visible = execute_tool(
            db,
            user_id=pair.user_b,
            name="find_similar_problems",
            arguments={"query": "部署失败"},
        )
    finally:
        _cleanup(db, pair)

    assert hidden["ok"] is True
    assert hidden["data"]["match"] is None
    assert visible["data"]["match"]["title"] == "only-user-b-cluster"


def test_list_actions_hides_other_users() -> None:
    _require_postgres()
    db = SessionLocal()
    pair = _seed(db)
    try:
        result = execute_tool(
            db,
            user_id=pair.user_a,
            name="list_actions",
            arguments={"focus": "all"},
        )
    finally:
        _cleanup(db, pair)

    titles = [item["title"] for item in result["data"]["items"]]
    assert "only-user-a-action" in titles
    assert "only-user-b-overdue" not in titles


def test_action_history_hides_other_users() -> None:
    _require_postgres()
    db = SessionLocal()
    pair = _seed(db)
    try:
        hidden = execute_tool(
            db,
            user_id=pair.user_a,
            name="get_action_history",
            arguments={"action_id": f"action:{pair.action_b}"},
        )
        visible = execute_tool(
            db,
            user_id=pair.user_b,
            name="get_action_history",
            arguments={"action_id": str(pair.action_b)},
        )
    finally:
        _cleanup(db, pair)

    assert hidden["data"]["found"] is False
    assert hidden["data"]["events"] == []
    assert "only-user-b-note" not in json.dumps(hidden["data"], ensure_ascii=False)
    notes = [event["note"] for event in visible["data"]["events"]]
    assert "only-user-b-note" in notes


def test_trends_hides_other_users() -> None:
    _require_postgres()
    db = SessionLocal()
    pair = _seed(db)
    try:
        hidden = execute_tool(db, user_id=pair.user_a, name="get_trends", arguments={})
        visible = execute_tool(db, user_id=pair.user_b, name="get_trends", arguments={})
    finally:
        _cleanup(db, pair)

    assert hidden["data"]["overdue_actions"] == 0
    hidden_titles = [item["title"] for item in hidden["data"]["overdue_items"]]
    assert "only-user-b-overdue" not in hidden_titles
    visible_titles = [item["title"] for item in visible["data"]["overdue_items"]]
    assert "only-user-b-overdue" in visible_titles


class _Pair:
    def __init__(self, user_a: UUID, user_b: UUID, action_b: UUID) -> None:
        self.user_a = user_a
        self.user_b = user_b
        self.action_b = action_b


def _seed(db: Session) -> _Pair:
    user_a = uuid4()
    user_b = uuid4()
    retro_a = uuid4()
    retro_b = uuid4()
    problem_a = uuid4()
    problem_b = uuid4()
    action_a = uuid4()
    action_b = uuid4()
    cluster_b = uuid4()
    vector = [1.0] + [0.0] * (settings.embedding_dim - 1)

    db.add(_user(user_a, "tool-a"))
    db.add(_user(user_b, "tool-b"))
    db.flush()
    db.add(_retro(retro_a, user_a))
    db.add(_retro(retro_b, user_b))
    db.flush()
    db.add(
        ProblemCluster(
            id=cluster_b,
            user_id=user_b,
            canonical_title="only-user-b-cluster",
            category="delivery",
            representative_embedding=vector,
        )
    )
    db.flush()
    db.add(_problem(problem_a, user_a, retro_a, None))
    db.add(_problem(problem_b, user_b, retro_b, cluster_b))
    db.flush()
    db.add(_action(action_a, user_a, retro_a, problem_a, "only-user-a-action", date(2099, 1, 1)))
    db.add(_action(action_b, user_b, retro_b, problem_b, "only-user-b-overdue", date(2020, 1, 1)))
    db.flush()
    db.add(_event(user_a, action_a, "only-user-a-note"))
    db.add(_event(user_b, action_b, "only-user-b-note"))
    db.commit()
    return _Pair(user_a, user_b, action_b)


def _cleanup(db: Session, pair: _Pair) -> None:
    db.rollback()
    db.execute(delete(User).where(User.id.in_([pair.user_a, pair.user_b])))
    db.commit()
    db.close()


def _fake_action(title: str, status: str, due_date: date) -> ActionItemOut:
    return ActionItemOut(
        id=uuid4(),
        retro_id=uuid4(),
        problem_occurrence_id=uuid4(),
        title=title,
        description="desc",
        owner="owner",
        due_date=due_date,
        success_criteria="criteria",
        status=status,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _unused_db() -> Session:
    return None  # type: ignore[return-value]


def _require_postgres() -> None:
    url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        pytest.skip(f"PostgreSQL not running: {exc}")


def _user(user_id: UUID, prefix: str) -> User:
    return User(
        id=user_id,
        email=f"{prefix}-{user_id.hex[:8]}@example.com",
        password_hash="x",
        locale="zh-CN",
    )


def _retro(retro_id: UUID, user_id: UUID) -> Retro:
    return Retro(
        id=retro_id,
        user_id=user_id,
        type="sprint",
        title="retro",
        review_date=date(2026, 8, 17),
        raw_content="content",
        status="published",
        index_status="ready",
    )


def _problem(
    problem_id: UUID,
    user_id: UUID,
    retro_id: UUID,
    cluster_id: UUID | None,
) -> ProblemOccurrence:
    return ProblemOccurrence(
        id=problem_id,
        user_id=user_id,
        retro_id=retro_id,
        title="problem",
        normalized_statement="problem",
        category="delivery",
        severity="high",
        source_quote="quote",
        disposition="kept",
        match_status="auto_linked" if cluster_id else "pending",
        cluster_id=cluster_id,
    )


def _action(
    action_id: UUID,
    user_id: UUID,
    retro_id: UUID,
    problem_id: UUID,
    title: str,
    due_date: date,
) -> ActionItem:
    return ActionItem(
        id=action_id,
        user_id=user_id,
        retro_id=retro_id,
        problem_occurrence_id=problem_id,
        title=title,
        description="desc",
        owner="owner",
        due_date=due_date,
        success_criteria="criteria",
        status="open",
    )


def _event(user_id: UUID, action_id: UUID, note: str) -> ActionEvent:
    return ActionEvent(
        id=uuid4(),
        user_id=user_id,
        action_id=action_id,
        event_type="created",
        from_status=None,
        to_status="open",
        note=note,
    )
