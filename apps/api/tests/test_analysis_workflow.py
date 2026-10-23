import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.agent_run import AgentRun
from app.providers.llm import LlmError
from app.repositories.actions import latest_action_statement
from app.services.retros import analyze_retro
from app.workflows.analysis import cite_prior, run_analysis_workflow


class _TraceSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        return None


class _RequestSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _extract() -> str:
    return json.dumps(
        {
            "summary": {"keep": ["发布前检查"], "decisions": [], "risks": []},
            "problems": [
                {
                    "title": "发布没有检查单",
                    "normalized_statement": "发布缺少检查单",
                    "source_quote": "这次发布又没走检查单",
                }
            ],
        },
        ensure_ascii=False,
    )


def _classify() -> str:
    return json.dumps(
        {"problems": [{"category": "process", "severity": "high"}]},
        ensure_ascii=False,
    )


def _diagnose() -> str:
    return json.dumps(
        {"items": [{"index": 0, "failure_reason": "上次驳回后没有补日志"}]},
        ensure_ascii=False,
    )


def _suggest(description: str = "发布前必须勾选检查单") -> str:
    return json.dumps(
        {
            "problems": [
                {
                    "suggested_actions": [
                        {
                            "title": "补上检查单",
                            "description": description,
                            "suggested_success_criteria": "检查单被勾选",
                        }
                    ]
                }
            ]
        },
        ensure_ascii=False,
    )


def _install_llm(monkeypatch: pytest.MonkeyPatch, replies: list[str]) -> list[list[dict[str, str]]]:
    pending = iter(replies)
    seen: list[list[dict[str, str]]] = []

    def chat_json(messages):
        seen.append(messages)
        try:
            return next(pending)
        except StopIteration as exc:
            raise AssertionError("unexpected model call") from exc

    monkeypatch.setattr("app.workflows.analysis.llm_provider.chat_json", chat_json)
    return seen


def _node_names(session: _TraceSession) -> list[str]:
    names: list[str] = []
    for obj in session.added:
        if isinstance(obj, AgentRun):
            names.append(obj.input[0]["content"])
    return names


def test_latest_action_query_stays_inside_the_users_cluster() -> None:
    user_id = uuid4()
    cluster_id = uuid4()
    statement = latest_action_statement(user_id, cluster_id)
    sql = str(statement)
    params = statement.compile().params
    assert "action_items.user_id" in sql
    assert "problem_occurrences.user_id" in sql
    assert "problem_occurrences.cluster_id" in sql
    assert "problem_occurrences.disposition" in sql
    assert user_id in params.values()
    assert cluster_id in params.values()


def test_recurring_suggestion_cites_status_and_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cluster_id = uuid4()
    action = SimpleNamespace(id=uuid4(), title="补检查单", status="in_progress")
    event = SimpleNamespace(event_type="rejected", note="没有发布日志")
    calls = {"history": 0}
    seen = _install_llm(monkeypatch, [_extract(), _classify(), _diagnose(), _suggest()])
    monkeypatch.setattr(
        "app.workflows.analysis.embedding_provider.embed_texts",
        lambda texts: [[0.1, 0.2]],
    )
    monkeypatch.setattr(
        "app.workflows.analysis.clusters_repo.find_nearest_cluster",
        lambda db, user_id, vector: (SimpleNamespace(id=cluster_id), 0.91),
    )

    def latest(db, user_id, cluster_id):
        calls["history"] += 1
        return action

    monkeypatch.setattr("app.workflows.analysis.actions_repo.latest_action_for_cluster", latest)
    monkeypatch.setattr(
        "app.workflows.analysis.actions_repo.list_events_for_action",
        lambda db, user_id, action_id: [event],
    )
    traces = _TraceSession()
    result = run_analysis_workflow(
        SimpleNamespace(),
        user_id=uuid4(),
        retro_type="release",
        title="发布复盘",
        review_date="2026-10-23",
        raw_content="这次发布又没走检查单",
        session_factory=lambda: traces,
    )
    description = result.problems[0].suggested_actions[0].description
    assert "上次行动状态：in_progress" in description
    assert "驳回原因：没有发布日志" in description
    assert calls["history"] == 1
    assert _node_names(traces) == ["extract", "classify", "match", "history", "diagnose", "suggest"]
    assert "上次驳回后没有补日志" in seen[-1][1]["content"]
    assert all(run.status == "ok" for run in traces.added if isinstance(run, AgentRun))


def test_a_new_problem_skips_history(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _install_llm(monkeypatch, [_extract(), _classify(), _suggest("只写检查单")])
    monkeypatch.setattr(
        "app.workflows.analysis.embedding_provider.embed_texts",
        lambda texts: [[0.1]],
    )
    monkeypatch.setattr(
        "app.workflows.analysis.clusters_repo.find_nearest_cluster",
        lambda db, user_id, vector: (SimpleNamespace(id=uuid4()), 0.2),
    )

    def latest(*args, **kwargs):
        raise AssertionError("history lookup should not run")

    monkeypatch.setattr("app.workflows.analysis.actions_repo.latest_action_for_cluster", latest)
    traces = _TraceSession()
    result = run_analysis_workflow(
        SimpleNamespace(),
        user_id=uuid4(),
        retro_type="release",
        title="发布复盘",
        review_date="2026-10-23",
        raw_content="第一次提到检查单",
        session_factory=lambda: traces,
    )
    assert result.problems[0].suggested_actions[0].description == "只写检查单"
    assert "history" not in _node_names(traces)
    assert "diagnose" not in _node_names(traces)
    assert len(seen) == 3


def test_a_failing_node_is_recorded_and_stops_the_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    def chat_json(messages):
        if any("归类" in message["content"] for message in messages):
            raise LlmError("llm_timeout")
        return _extract()

    monkeypatch.setattr("app.workflows.analysis.llm_provider.chat_json", chat_json)
    monkeypatch.setattr(
        "app.workflows.analysis.embedding_provider.embed_texts",
        lambda texts: (_ for _ in ()).throw(AssertionError("match should not run")),
    )
    traces = _TraceSession()
    with pytest.raises(LlmError) as exc:
        run_analysis_workflow(
            SimpleNamespace(),
            user_id=uuid4(),
            retro_type="release",
            title="发布复盘",
            review_date="2026-10-23",
            raw_content="原文",
            session_factory=lambda: traces,
        )
    assert exc.value.message == "llm_timeout"
    runs = [obj for obj in traces.added if isinstance(obj, AgentRun)]
    assert [run.input[0]["content"] for run in runs] == ["extract", "classify"]
    assert [run.status for run in runs] == ["ok", "error"]


def test_analyze_retro_still_rolls_back_and_marks_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    retro = SimpleNamespace(
        id=uuid4(),
        status="draft",
        analysis_error=None,
        type="release",
        title="发布复盘",
        review_date=date(2026, 10, 23),
        raw_content="原文",
    )
    monkeypatch.setattr(
        "app.services.retros.retros_repo.get_retro_for_user",
        lambda db, user_id, retro_id: retro,
    )

    def boom(*args, **kwargs):
        raise LlmError("llm_timeout")

    monkeypatch.setattr("app.services.retros.run_analysis_workflow", boom)
    db = _RequestSession()
    with pytest.raises(HTTPException) as exc:
        analyze_retro(db, SimpleNamespace(id=uuid4()), retro.id)  # type: ignore[arg-type]
    assert exc.value.status_code == 502
    assert exc.value.detail == {"code": "llm_timeout"}
    assert db.rollbacks == 1
    assert retro.status == "analysis_failed"
    assert retro.analysis_error == "llm_timeout"


def test_cite_prior_does_not_repeat_a_reason_already_present() -> None:
    problem = {
        "prior_status": "in_progress",
        "prior_reject_reason": "没有发布日志",
    }
    text = cite_prior("已经写了没有发布日志", problem)  # type: ignore[arg-type]
    assert text.count("没有发布日志") == 1
    assert "上次行动状态：in_progress" in text


def test_cite_prior_keeps_the_citation_inside_the_description_limit() -> None:
    problem = {"prior_status": "in_progress", "prior_reject_reason": "没有发布日志"}
    text = cite_prior("记" * 5000, problem)  # type: ignore[arg-type]
    assert len(text) <= 5000
    assert text.endswith("（上次行动状态：in_progress；驳回原因：没有发布日志）")
