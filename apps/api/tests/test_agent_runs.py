from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.main import app
from app.repositories.agent_runs import list_runs_statement, list_steps_statement
from app.services.agent_runs import get_run, list_runs


class _Rows:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _Session:
    def __init__(self, run: object | None = None, rows: list[object] | None = None) -> None:
        self.run = run
        self.rows = rows or []
        self.scalar_calls = 0

    def get(self, model: type, ident: object) -> object | None:
        if self.run is not None and getattr(self.run, "id", None) == ident:
            return self.run
        return None

    def scalars(self, stmt: object) -> _Rows:
        self.scalar_calls += 1
        return _Rows(self.rows)


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _run(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "kind": "chat",
        "status": "answered",
        "input": [
            {"role": "system", "content": "系统提示，不要展示"},
            {"role": "user", "content": "部署为什么失败"},
        ],
        "output": "配置写错。",
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "duration_ms": 842,
        "created_at": datetime(2026, 10, 23, 2, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_routes_expose_run_list_and_detail() -> None:
    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/agent/runs"]
    assert "get" in paths["/api/v1/agent/runs/{run_id}"]


def test_list_query_belongs_to_the_current_user() -> None:
    user_id = uuid4()
    statement = list_runs_statement(user_id)
    sql = str(statement)
    params = statement.compile().params
    assert "agent_runs.user_id" in sql
    assert "agent_runs.created_at DESC" in sql
    assert user_id in params.values()
    assert 51 in params.values()


def test_step_query_orders_by_step_index() -> None:
    run_id = uuid4()
    statement = list_steps_statement(run_id)
    sql = str(statement)
    params = statement.compile().params
    assert "agent_steps.run_id" in sql
    assert "agent_steps.step_index ASC" in sql
    assert run_id in params.values()


def test_list_shows_the_user_question_and_tokens() -> None:
    user = _user()
    run = _run(user_id=user.id)
    listed = list_runs(_Session(rows=[run]), user)  # type: ignore[arg-type]
    assert listed.limited is False
    assert len(listed.items) == 1
    item = listed.items[0]
    assert item.question == "部署为什么失败"
    assert "系统提示" not in item.question
    assert item.prompt_tokens == 11
    assert item.completion_tokens == 7
    assert item.duration_ms == 842
    assert item.status == "answered"


def test_list_preview_stops_at_160_characters() -> None:
    user = _user()
    long_question = "部" * 180
    run = _run(
        user_id=user.id,
        input=[{"role": "user", "content": long_question}],
    )
    listed = list_runs(_Session(rows=[run]), user)  # type: ignore[arg-type]
    assert listed.items[0].question == f"{'部' * 160}…"
    detail = get_run(_Session(run=run), user, run.id)  # type: ignore[arg-type]
    assert detail.question == long_question


def test_list_marks_when_more_than_50_runs_exist() -> None:
    user = _user()
    rows = [_run(user_id=user.id, input=[{"role": "user", "content": str(i)}]) for i in range(51)]
    listed = list_runs(_Session(rows=rows), user)  # type: ignore[arg-type]
    assert listed.limited is True
    assert len(listed.items) == 50
    assert listed.items[0].question == "0"


def test_detail_includes_steps_for_the_owner() -> None:
    user = _user()
    run = _run(user_id=user.id)
    step = SimpleNamespace(
        step_index=2,
        step_type="tool",
        tool_name="search_retro_content",
        arguments={"query": "部署"},
        result_summary="命中 1 条",
        error=None,
        prompt_tokens=0,
        completion_tokens=0,
        duration_ms=40,
    )
    session = _Session(run=run, rows=[step])
    detail = get_run(session, user, run.id)  # type: ignore[arg-type]
    assert detail.question == "部署为什么失败"
    assert detail.output == "配置写错。"
    assert detail.prompt_tokens == 11
    assert len(detail.steps) == 1
    assert detail.steps[0].tool_name == "search_retro_content"
    assert detail.steps[0].duration_ms == 40
    assert detail.steps[0].prompt_tokens == 0
    assert session.scalar_calls == 1


def test_other_users_run_is_hidden_without_loading_steps() -> None:
    owner = _user()
    stranger = _user()
    run = _run(user_id=owner.id)
    session = _Session(run=run, rows=[])
    with pytest.raises(HTTPException) as exc:
        get_run(session, stranger, run.id)  # type: ignore[arg-type]
    assert exc.value.status_code == 404
    assert exc.value.detail == {"code": "run_not_found"}
    assert session.scalar_calls == 0


def test_missing_run_is_not_found() -> None:
    session = _Session()
    with pytest.raises(HTTPException) as exc:
        get_run(session, _user(), uuid4())  # type: ignore[arg-type]
    assert exc.value.status_code == 404
    assert exc.value.detail == {"code": "run_not_found"}
