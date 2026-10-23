"""Build a Markdown eval report.

Retrieval numbers come from a fixed vector ranking plus the real BM25/RRF code.
Model metrics stay unmeasured until a prediction file is supplied.
"""

import json
from pathlib import Path
from uuid import UUID, uuid5

from app.evals.corpus import DEMO_CHUNK_TEXTS, DISTRACTOR_TEXTS
from app.evals.metrics import mean, recall_at_k
from app.retrieval.search import rank_bm25, rrf_fuse

CASES_PATH = Path(__file__).resolve().parents[2] / "evals" / "cases.jsonl"
REPORT_PATH = Path(__file__).resolve().parents[2] / "evals" / "report.md"
RECALL_K = 5
_NAMESPACE = UUID("6c1b4e3a-7d2f-4a8b-9c0d-111111111111")


class _Chunk:
    def __init__(self, content: str, vector_score: float) -> None:
        self.id = uuid5(_NAMESPACE, content)
        self.content = content
        self.vector_score = vector_score


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def fixture_chunks() -> list[_Chunk]:
    """Distractors outrank the demo sentences on the fixed vector score."""
    chunks = [_Chunk(text, 0.95 - index * 0.05) for index, text in enumerate(DISTRACTOR_TEXTS)]
    chunks.extend(_Chunk(text, 0.05) for text in DEMO_CHUNK_TEXTS)
    return chunks


def vector_ids(chunks: list[_Chunk], limit: int) -> list[str]:
    ordered = sorted(chunks, key=lambda chunk: (-chunk.vector_score, str(chunk.id)))
    return [str(chunk.id) for chunk in ordered[:limit]]


def hybrid_ids(query: str, chunks: list[_Chunk], limit: int) -> list[str]:
    vector = sorted(chunks, key=lambda chunk: (-chunk.vector_score, str(chunk.id)))[:10]
    keyword = rank_bm25(query, chunks, 10)  # type: ignore[arg-type]
    if not keyword:
        return [str(chunk.id) for chunk in vector[:limit]]
    fused = rrf_fuse([vector, keyword], k=60)  # type: ignore[arg-type]
    return [str(chunk.id) for chunk, _score in fused[:limit]]


def retrieval_counts(cases: list[dict], chunks: list[_Chunk]) -> tuple[int, int, int]:
    """Return (vector hits, hybrid hits, query count) for chunk-labeled questions."""
    queries = [
        case
        for case in cases
        if case["kind"] == "qa" and case["expected"]["source"] == "chunk"
    ]
    vector_hits = 0
    hybrid_hits = 0
    for case in queries:
        relevant = {
            str(chunk.id)
            for chunk in chunks
            if all(quote in chunk.content for quote in case["expected"]["must_include"])
        }
        if not relevant:
            raise ValueError(f"{case['id']} does not match a demo chunk")
        question = case["input"]["question"]
        vector_hits += int(recall_at_k(vector_ids(chunks, RECALL_K), relevant, RECALL_K) == 1.0)
        hybrid_hits += int(recall_at_k(hybrid_ids(question, chunks, RECALL_K), relevant, RECALL_K) == 1.0)
    return vector_hits, hybrid_hits, len(queries)


def build_report(cases: list[dict] | None = None) -> str:
    labeled = cases if cases is not None else load_cases()
    vector_hits, hybrid_hits, total = retrieval_counts(labeled, fixture_chunks())
    counts = _counts(labeled)
    return "\n".join(
        [
            "# RetroFlow 评测报告",
            "",
            "跑法：`python -m app.evals.report`。同一份 `evals/cases.jsonl` 和同一套固定向量名次，两次运行的检索数字相同。",
            "",
            "下面的 Recall@5 用的是夹具：6 条无关短文的向量分高于 3 条演示复盘。它说明混合检索能把关键词捞回来。它不是 Ollama 在 Postgres 上的真实召回，不要把这个 1.00 写进简历当成线上成绩。",
            "",
            "## 检索对比（离线夹具）",
            "",
            "| 指标 | 结果 |",
            "| --- | --- |",
            f"| Recall@{RECALL_K} 纯向量 | {_rate(vector_hits, total)} |",
            f"| Recall@{RECALL_K} 混合（向量名次 + BM25，RRF k=60） | {_rate(hybrid_hits, total)} |",
            "",
            "问题是标注里 `source=chunk` 的问答。命中指前 5 条里出现包含 `must_include` 原句的那一条演示复盘。",
            "",
            "## 尚未测量",
            "",
            "这些指标要有一次真实模型运行的记录才能算。这次没有调用 DeepSeek，也没有连 Postgres，所以不填 0，避免把「没跑」看成「很差」或「满分」。",
            "",
            "| 指标 | 结果 | 定义 |",
            "| --- | --- | --- |",
            f"| 工具选择正确率 | 未测量 | 标注要求的工具都出现在本次调用里。分母是 {counts['qa']} 条问答。 |",
            "| 引用有效率 | 未测量 | 回答为 answered 时，must_include 的原句都在回答里；该拒答时状态是 insufficient_evidence。 |",
            f"| 验收判断准确率 | 未测量 | 建议的 pass/reject 与标注一致。分母是 {counts['verify']} 条验收。 |",
            f"| 注入拦截率 | 未测量 | 运行里没有出现标注禁止的动作。分母是 {counts['injection']} 条注入。 |",
            "| 平均步数 | 未测量 | 每条问答的工具调用次数取平均。 |",
            "| 平均耗时 | 未测量 | 每条运行的 duration_ms 取平均。 |",
            "| 平均 Token | 未测量 | prompt_tokens 与 completion_tokens 之和取平均。 |",
            "",
            "## 用例规模",
            "",
            f"- 问答 {counts['qa']}",
            f"- 复发 {counts['recurrence']}",
            f"- 验收 {counts['verify']}",
            f"- 注入 {counts['injection']}",
            "",
        ]
    )


def write_report(path: Path = REPORT_PATH) -> Path:
    path.write_text(build_report(), encoding="utf-8")
    return path


def main() -> None:
    print(write_report())


def _counts(cases: list[dict]) -> dict[str, int]:
    counts = {"qa": 0, "recurrence": 0, "verify": 0, "injection": 0}
    for case in cases:
        counts[case["kind"]] += 1
    return counts


def _rate(hits: int, total: int) -> str:
    if total == 0:
        return "未测量"
    return f"{hits}/{total} = {mean([1.0] * hits + [0.0] * (total - hits)):.2f}"


if __name__ == "__main__":
    main()
