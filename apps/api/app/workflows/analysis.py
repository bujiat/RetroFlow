import json
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from app.agent.tracing import TraceEvent, begin_agent_run, finish_agent_run, summarize
from app.core.config import settings
from app.core.db import SessionLocal
from app.providers import embedding as embedding_provider
from app.providers import llm as llm_provider
from app.providers.prompts import build_repair_user_prompt
from app.repositories import actions as actions_repo
from app.repositories import clusters as clusters_repo
from app.schemas.analysis import (
    AnalysisProblem,
    AnalysisSummary,
    LlmAnalysisResult,
    ProblemCategory,
    ProblemSeverity,
    SuggestedActionDraft,
)

_EXTRACT_SYSTEM = """你是研发复盘分析助手。从复盘原文提取问题和摘要。

只输出一个 JSON 对象，不要 Markdown。

{
  "summary": {
    "keep": ["string"],
    "decisions": [{ "decision": "string", "reason": "string" }],
    "risks": [{ "risk": "string", "suggestion": "string" }]
  },
  "problems": [
    { "title": "string", "normalized_statement": "string", "source_quote": "string" }
  ]
}

规则：problems 最多 5 条；source_quote 必须来自原文；没有具体问题就给空数组；不要写行动建议。
"""

_CLASSIFY_SYSTEM = """你给已经提取出的问题归类。只输出 JSON。

{ "problems": [{ "category": "process|quality|delivery|collaboration|reliability|tooling|other", "severity": "low|medium|high" }] }

problems 的数量和顺序必须与输入一致。
"""

_DIAGNOSE_SYSTEM = """你根据上次行动的状态和驳回原因，用一句话说明这次复发可能卡在哪里。只输出 JSON。

{ "items": [{ "index": 0, "failure_reason": "string" }] }

只能使用输入里给出的事实。items 必须覆盖输入中的每个 index。
"""

_SUGGEST_SYSTEM = """你为每个问题写 1～3 条改进行动。只输出 JSON。

{ "problems": [{ "suggested_actions": [{ "title": "string", "description": "string", "suggested_success_criteria": "string" }] }] }

数量和顺序必须与输入一致。若输入里有上次行动状态或驳回原因，description 必须写上这些原话。
"""


class DraftProblem(TypedDict):
    title: str
    normalized_statement: str
    source_quote: str
    category: str
    severity: str
    recurring: bool
    cluster_id: str | None
    prior_title: str | None
    prior_status: str | None
    prior_reject_reason: str | None
    failure_reason: str
    suggested_actions: list[dict[str, str]]


class AnalysisState(TypedDict):
    retro_type: str
    title: str
    review_date: str
    raw_content: str
    summary: dict[str, object]
    problems: list[DraftProblem]


class _ExtractedProblem(BaseModel):
    title: str = Field(min_length=1)
    normalized_statement: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)


class _ExtractResult(BaseModel):
    summary: AnalysisSummary
    problems: list[_ExtractedProblem] = Field(default_factory=list, max_length=5)


class _Classified(BaseModel):
    category: ProblemCategory
    severity: ProblemSeverity


class _ClassifyResult(BaseModel):
    problems: list[_Classified]


class _Diagnosis(BaseModel):
    index: int
    failure_reason: str = Field(min_length=1)


class _DiagnoseResult(BaseModel):
    items: list[_Diagnosis]


class _SuggestedProblem(BaseModel):
    suggested_actions: list[SuggestedActionDraft] = Field(min_length=1, max_length=3)


class _SuggestResult(BaseModel):
    problems: list[_SuggestedProblem]


_DESCRIPTION_LIMIT = 5000


def cite_prior(description: str, problem: DraftProblem) -> str:
    """Keep the previous action's status or rejection reason in the suggestion text."""
    extras: list[str] = []
    status = problem["prior_status"]
    reason = problem["prior_reject_reason"]
    if status and status not in description:
        extras.append(f"上次行动状态：{status}")
    if reason and reason not in description:
        extras.append(f"驳回原因：{reason}")
    if not extras:
        return description
    suffix = f"（{'；'.join(extras)}）"
    room = _DESCRIPTION_LIMIT - len(suffix)
    if room < 1:
        return suffix[:_DESCRIPTION_LIMIT]
    body = description if len(description) <= room else description[:room].rstrip()
    return f"{body}{suffix}"


def run_analysis_workflow(
    db: Session,
    *,
    user_id: UUID,
    retro_type: str,
    title: str,
    review_date: str,
    raw_content: str,
    session_factory: Callable[[], Session] | None = None,
) -> LlmAnalysisResult:
    """Run the fixed analysis graph. Each node records its own run. Raises on failure."""
    opener = session_factory or SessionLocal
    graph = _compile(db, user_id, opener)
    result = graph.invoke(
        {
            "retro_type": retro_type,
            "title": title,
            "review_date": review_date,
            "raw_content": raw_content,
            "summary": {"keep": [], "decisions": [], "risks": []},
            "problems": [],
        }
    )
    return _to_analysis(result)


def _compile(db: Session, user_id: UUID, opener: Callable[[], Session]):
    def traced(name: str, fn: Callable[[AnalysisState], dict[str, object]]):
        def node(state: AnalysisState) -> dict[str, object]:
            started = perf_counter()
            try:
                update = fn(state)
            except Exception as exc:
                _record(opener, user_id, name, "error", None, _error_text(exc), started)
                raise
            _record(opener, user_id, name, "ok", summarize(update), None, started)
            return update

        return node

    graph = StateGraph(AnalysisState)
    graph.add_node("extract", traced("extract", _extract))
    graph.add_node("classify", traced("classify", _classify))
    graph.add_node("match", traced("match", lambda state: _match(db, user_id, state)))
    graph.add_node("history", traced("history", lambda state: _history(db, user_id, state)))
    graph.add_node("diagnose", traced("diagnose", _diagnose))
    graph.add_node("suggest", traced("suggest", _suggest))
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "classify")
    graph.add_edge("classify", "match")
    graph.add_conditional_edges("match", _route_after_match)
    graph.add_edge("history", "diagnose")
    graph.add_edge("diagnose", "suggest")
    graph.add_edge("suggest", END)
    return graph.compile()


def _route_after_match(state: AnalysisState) -> str:
    if any(problem["recurring"] for problem in state["problems"]):
        return "history"
    return "suggest"


def _extract(state: AnalysisState) -> dict[str, object]:
    parsed = _chat_model(
        _EXTRACT_SYSTEM,
        _retro_block(state),
        _ExtractResult,
    )
    problems = [_blank_problem(item) for item in parsed.problems]
    return {"summary": parsed.summary.model_dump(), "problems": problems}


def _classify(state: AnalysisState) -> dict[str, object]:
    if not state["problems"]:
        return {}
    payload = [
        {"title": problem["title"], "normalized_statement": problem["normalized_statement"]}
        for problem in state["problems"]
    ]
    parsed = _chat_model(_CLASSIFY_SYSTEM, _json(payload), _ClassifyResult)
    _require_same_length(len(state["problems"]), len(parsed.problems), "classify")
    problems: list[DraftProblem] = []
    for problem, label in zip(state["problems"], parsed.problems, strict=True):
        copied = dict(problem)
        copied["category"] = label.category
        copied["severity"] = label.severity
        problems.append(copied)
    return {"problems": problems}


def _match(db: Session, user_id: UUID, state: AnalysisState) -> dict[str, object]:
    if not state["problems"]:
        return {}
    vectors = embedding_provider.embed_texts(
        [f"{problem['title']}\n{problem['normalized_statement']}" for problem in state["problems"]]
    )
    problems: list[DraftProblem] = []
    for problem, vector in zip(state["problems"], vectors, strict=True):
        copied = dict(problem)
        nearest = clusters_repo.find_nearest_cluster(db, user_id=user_id, vector=vector)
        if nearest is not None and nearest[1] >= settings.problem_match_threshold:
            copied["recurring"] = True
            copied["cluster_id"] = str(nearest[0].id)
        else:
            copied["recurring"] = False
            copied["cluster_id"] = None
        problems.append(copied)
    return {"problems": problems}


def _history(db: Session, user_id: UUID, state: AnalysisState) -> dict[str, object]:
    problems: list[DraftProblem] = []
    for problem in state["problems"]:
        copied = dict(problem)
        if copied["recurring"] and copied["cluster_id"]:
            action = actions_repo.latest_action_for_cluster(
                db,
                user_id=user_id,
                cluster_id=UUID(copied["cluster_id"]),
            )
            if action is not None:
                copied["prior_title"] = action.title
                copied["prior_status"] = action.status
                copied["prior_reject_reason"] = _reject_reason(db, user_id, action.id)
        problems.append(copied)
    return {"problems": problems}


def _diagnose(state: AnalysisState) -> dict[str, object]:
    indexed = [
        {
            "index": index,
            "title": problem["title"],
            "prior_status": problem["prior_status"],
            "prior_reject_reason": problem["prior_reject_reason"],
        }
        for index, problem in enumerate(state["problems"])
        if problem["prior_status"]
    ]
    if not indexed:
        return {}
    parsed = _chat_model(_DIAGNOSE_SYSTEM, _json(indexed), _DiagnoseResult)
    reasons = {item.index: item.failure_reason.strip() for item in parsed.items}
    expected = {item["index"] for item in indexed}
    if set(reasons) != expected:
        _fail_validation("diagnose")
    problems: list[DraftProblem] = []
    for index, problem in enumerate(state["problems"]):
        copied = dict(problem)
        if index in reasons:
            copied["failure_reason"] = reasons[index]
        problems.append(copied)
    return {"problems": problems}


def _suggest(state: AnalysisState) -> dict[str, object]:
    if not state["problems"]:
        return {}
    payload = [
        {
            "title": problem["title"],
            "normalized_statement": problem["normalized_statement"],
            "failure_reason": problem["failure_reason"],
            "prior_status": problem["prior_status"],
            "prior_reject_reason": problem["prior_reject_reason"],
        }
        for problem in state["problems"]
    ]
    parsed = _chat_model(_SUGGEST_SYSTEM, _json(payload), _SuggestResult)
    _require_same_length(len(state["problems"]), len(parsed.problems), "suggest")
    problems: list[DraftProblem] = []
    for problem, suggestion in zip(state["problems"], parsed.problems, strict=True):
        copied = dict(problem)
        actions = []
        for action in suggestion.suggested_actions:
            description = cite_prior(action.description, problem)
            actions.append(
                {
                    "title": action.title,
                    "description": description,
                    "suggested_success_criteria": action.suggested_success_criteria,
                }
            )
        copied["suggested_actions"] = actions
        problems.append(copied)
    return {"problems": problems}


def _blank_problem(item: _ExtractedProblem) -> DraftProblem:
    return {
        "title": item.title.strip(),
        "normalized_statement": item.normalized_statement.strip(),
        "source_quote": item.source_quote.strip(),
        "category": "other",
        "severity": "medium",
        "recurring": False,
        "cluster_id": None,
        "prior_title": None,
        "prior_status": None,
        "prior_reject_reason": None,
        "failure_reason": "",
        "suggested_actions": [],
    }


def _reject_reason(db: Session, user_id: UUID, action_id: UUID) -> str | None:
    events = actions_repo.list_events_for_action(db, user_id=user_id, action_id=action_id)
    for event in reversed(events):
        if event.event_type == "rejected" and event.note:
            return event.note.strip()
    return None


def _to_analysis(state: AnalysisState) -> LlmAnalysisResult:
    return LlmAnalysisResult(
        summary=AnalysisSummary.model_validate(state["summary"]),
        problems=[
            AnalysisProblem(
                title=problem["title"],
                normalized_statement=problem["normalized_statement"],
                category=problem["category"],
                severity=problem["severity"],
                source_quote=problem["source_quote"],
                suggested_actions=[
                    SuggestedActionDraft.model_validate(action)
                    for action in problem["suggested_actions"]
                ],
            )
            for problem in state["problems"]
        ],
    )


def _chat_model(system: str, user_text: str, model: type[BaseModel]) -> BaseModel:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]
    raw = llm_provider.chat_json(messages)
    try:
        return model.model_validate_json(raw)
    except ValidationError as first_error:
        repaired = llm_provider.chat_json(
            [
                *messages,
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": build_repair_user_prompt(
                        previous_output=raw,
                        validation_error=str(first_error),
                    ),
                },
            ]
        )
        return model.model_validate_json(repaired)


def _require_same_length(expected: int, actual: int, node: str) -> None:
    if expected != actual:
        _fail_validation(node)


def _fail_validation(node: str) -> None:
    class _Mismatch(BaseModel):
        node: str

        @model_validator(mode="after")
        def reject(self) -> "_Mismatch":
            raise ValueError(f"{self.node}_count_mismatch")

    _Mismatch(node=node)


def _retro_block(state: AnalysisState) -> str:
    return (
        f"复盘类型：{state['retro_type']}\n"
        f"标题：{state['title']}\n"
        f"日期：{state['review_date']}\n\n"
        f"复盘原文：\n---\n{state['raw_content']}\n---"
    )


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _error_text(exc: Exception) -> str:
    message = getattr(exc, "message", None)
    if isinstance(message, str) and message:
        return message
    return str(exc)


def _record(
    opener: Callable[[], Session],
    user_id: UUID,
    node: str,
    status: str,
    output: str | None,
    error: str | None,
    started: float,
) -> None:
    db = opener()
    try:
        run = begin_agent_run(
            db,
            user_id=user_id,
            kind="analysis",
            messages=[{"role": "user", "content": node}],
            started_at=datetime.now(UTC),
        )
        finish_agent_run(
            db,
            run,
            status=status,
            output=output,
            prompt_tokens=0,
            completion_tokens=0,
            duration_ms=max(0, int((perf_counter() - started) * 1000)),
            events=[
                TraceEvent(
                    step_type="llm" if node in {"extract", "classify", "diagnose", "suggest"} else "tool",
                    tool_name=None if node in {"extract", "classify", "diagnose", "suggest"} else node,
                    arguments=None,
                    result_summary=output,
                    error=error,
                    prompt_tokens=0,
                    completion_tokens=0,
                    duration_ms=max(0, int((perf_counter() - started) * 1000)),
                )
            ],
        )
        db.commit()
    finally:
        db.close()
