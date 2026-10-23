from pathlib import Path

from app.evals.metrics import (
    citation_valid,
    decision_correct,
    injection_blocked,
    mean,
    recall_at_k,
    tool_selection_correct,
)
from app.evals.report import (
    build_report,
    fixture_chunks,
    load_cases,
    retrieval_counts,
    write_report,
)


def test_metric_formulas() -> None:
    assert recall_at_k(["a", "b", "c"], {"c"}, k=2) == 0.0
    assert recall_at_k(["a", "b", "c"], {"c"}, k=5) == 1.0
    assert tool_selection_correct(["search_retro_content", "list_actions"], ["list_actions"])
    assert citation_valid(
        status="answered",
        answer="发现数据库迁移没有跑",
        must_include=["数据库迁移没有跑"],
    )
    assert citation_valid(status="insufficient_evidence", answer="原文里没有", must_include=[])
    assert not citation_valid(status="answered", answer="用的是 AWS", must_include=[])
    assert decision_correct("reject", "reject")
    assert injection_blocked(["search_retro_content"], ["verify_action"])
    assert not injection_blocked(["verify_action"], ["verify_action"])
    assert mean([]) is None
    assert mean([1.0, 0.0]) == 0.5


def test_offline_report_is_reproducible(tmp_path) -> None:
    first = build_report()
    second = build_report()
    assert first == second
    vector_hits, hybrid_hits, total = retrieval_counts(load_cases(), fixture_chunks())
    assert (vector_hits, hybrid_hits, total) == (0, 4, 4)
    assert "0/4 = 0.00" in first
    assert "4/4 = 1.00" in first
    assert "未测量" in first
    assert "不要把这个 1.00 写进简历" in first
    written = write_report(tmp_path / "report.md")
    assert written.read_text(encoding="utf-8") == first


def test_readme_quotes_the_same_retrieval_numbers() -> None:
    readme = Path(__file__).resolve().parents[3].joinpath("README.md").read_text(encoding="utf-8")
    report = build_report()
    for snippet in ("0/4 = 0.00", "4/4 = 1.00", "未测量"):
        assert snippet in report
        assert snippet in readme
    assert "线上召回" in readme
