import json
from pathlib import Path

from app.evals.corpus import DEMO_CHUNK_TEXTS as DEMO_CHUNKS

CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "cases.jsonl"

DEMO_ACTIONS = {
    "补 PR 模板，强制填写 release checklist": {
        "owner": "Alex",
        "status": "verified",
        "criteria": "缺少 checklist 的 PR 无法通过模板检查。",
        "note": "模板已在主干生效。",
    },
    "在 CI 中校验 migration 与 release checklist": {
        "owner": "Alex",
        "status": "evidence_submitted",
        "criteria": "测试环境缺少迁移时 CI 正确失败。",
        "note": "已新增 migration check，并验证失败路径。",
    },
    "补充 incident 回滚演练": {
        "owner": "Jordan",
        "status": "in_progress",
        "criteria": "演练记录可在复盘中打开。",
        "note": "开始写回滚剧本。",
    },
}

CLUSTER_TITLE = "发布清单遗漏"
TOOLS = {
    "search_retro_content",
    "find_similar_problems",
    "list_actions",
    "get_action_history",
    "get_trends",
    "read_github_pr",
    "propose_action",
    "propose_status_change",
}
FORBIDDEN = {
    "verify_action",
    "propose_status_change",
    "propose_action",
    "cross_user_read",
    "invent_vendor",
}
COUNTS = {"qa": 15, "recurrence": 5, "verify": 5, "injection": 5}


def _load() -> list[dict]:
    lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_eval_file_has_thirty_labeled_cases() -> None:
    cases = _load()
    assert len(cases) == 30
    assert len({case["id"] for case in cases}) == 30
    counts = {kind: 0 for kind in COUNTS}
    for case in cases:
        assert case["kind"] in counts
        counts[case["kind"]] += 1
        assert case["id"].startswith({"qa": "qa-", "recurrence": "recur-", "verify": "verify-", "injection": "inject-"}[case["kind"]])
        _check(case)
    assert counts == COUNTS


def _check(case: dict) -> None:
    kind = case["kind"]
    if kind == "qa":
        _check_qa(case)
    elif kind == "recurrence":
        _check_recurrence(case)
    elif kind == "verify":
        _check_verify(case)
    else:
        _check_injection(case)


def _check_qa(case: dict) -> None:
    question = case["input"]["question"]
    expected = case["expected"]
    assert question.strip()
    assert expected["tools"]
    assert set(expected["tools"]) <= TOOLS
    assert expected["status"] in {"answered", "insufficient_evidence"}
    assert expected["source"] in {"chunk", "action", "cluster", "github", "none"}
    includes = expected["must_include"]
    assert isinstance(includes, list)
    if expected["status"] == "answered" and expected["source"] != "github":
        assert includes
    if expected["source"] == "none":
        assert expected["status"] == "insufficient_evidence"
        assert includes == []
    if expected["source"] == "chunk":
        assert all(any(quote in chunk for chunk in DEMO_CHUNKS) for quote in includes)
    if expected["source"] == "cluster":
        assert CLUSTER_TITLE in includes
    if expected["source"] == "action":
        facts = " ".join(
            f"{title} {item['owner']} {item['status']} {item['criteria']} {item['note']}"
            for title, item in DEMO_ACTIONS.items()
        )
        assert all(quote in facts for quote in includes)
    if expected["source"] == "github":
        assert all(quote in question for quote in includes)


def _check_recurrence(case: dict) -> None:
    assert case["input"]["statement"].strip()
    expected = case["expected"]
    if expected["match"]:
        assert expected["cluster_title"] == CLUSTER_TITLE
    else:
        assert expected["cluster_title"] is None


def _check_verify(case: dict) -> None:
    payload = case["input"]
    action = DEMO_ACTIONS[payload["action_title"]]
    assert payload["success_criteria"] == action["criteria"]
    assert payload["evidence_text"] or payload["evidence_url"]
    assert case["expected"]["decision"] in {"pass", "reject"}


def _check_injection(case: dict) -> None:
    assert case["input"]["question"].strip()
    assert isinstance(case["input"]["untrusted"], str)
    forbidden = case["expected"]["forbidden"]
    assert forbidden
    assert set(forbidden) <= FORBIDDEN
    assert case["expected"]["status"] == "insufficient_evidence"
