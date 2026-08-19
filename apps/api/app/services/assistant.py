from __future__ import annotations

import json

from fastapi import status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import api_error
from app.models.user import User
from app.providers import embedding as embedding_provider
from app.providers import llm as llm_provider
from app.providers.prompts import ASSISTANT_SYSTEM_PROMPT, build_assistant_user_prompt
from app.repositories import assistant as assistant_repo
from app.repositories import chunks as chunks_repo
from app.schemas.assistant import (
    AssistantCitation,
    AssistantQueryRequest,
    AssistantQueryResponse,
)


class _LlmAssistantResult(BaseModel):
    status: str
    answer: str
    citation_ids: list[str] = Field(default_factory=list)


def query_assistant(
    db: Session,
    user: User,
    payload: AssistantQueryRequest,
) -> AssistantQueryResponse:
    question = payload.question.strip()
    if len(question) < 2:
        raise api_error(status.HTTP_400_BAD_REQUEST, "question_too_short")

    try:
        query_vector = embedding_provider.embed_texts([question])[0]
    except embedding_provider.EmbeddingError as exc:
        raise api_error(status.HTTP_502_BAD_GATEWAY, exc.message) from exc

    scored = chunks_repo.search_chunks(
        db,
        user_id=user.id,
        vector=query_vector,
        limit=settings.rag_retrieval_top_k,
    )
    scored = [(c, s) for c, s in scored if s >= settings.rag_min_score]
    scored = scored[: settings.rag_context_top_k]

    if not scored:
        return AssistantQueryResponse(
            status="insufficient_evidence",
            answer="还没有找到足够相近的复盘原文。可以先对几篇复盘点「重新分析」以建立索引，或换个更贴近历史记录的问法。",
            citations=[],
        )

    retro_ids = {chunk.retro_id for chunk, _ in scored}
    retros = assistant_repo.retros_by_ids(db, user_id=user.id, retro_ids=retro_ids)
    problems = assistant_repo.list_problems(db, user_id=user.id, retro_ids=retro_ids)
    actions = assistant_repo.list_actions(db, user_id=user.id, retro_ids=retro_ids)
    cluster_ids = [p.cluster_id for p in problems if p.cluster_id is not None][:5]
    clusters = (
        assistant_repo.clusters_by_ids(db, user_id=user.id, cluster_ids=cluster_ids)
        if cluster_ids
        else {}
    )

    citation_catalog: dict[str, AssistantCitation] = {}
    context_lines: list[str] = []

    for chunk, score in scored:
        cid = f"chunk:{chunk.id}"
        retro = retros.get(chunk.retro_id)
        title = retro.title if retro else "复盘原文"
        citation_catalog[cid] = AssistantCitation(
            id=cid,
            source_type="chunk",
            title=title,
            excerpt=chunk.content[:280],
            retro_id=chunk.retro_id,
            href_hint=f"/retro/{chunk.retro_id}/confirm",
        )
        context_lines.append(
            f"[{cid}] type=chunk score={score:.3f} retro={title}\n{chunk.content}"
        )

    for problem in problems:
        pid = f"problem:{problem.id}"
        citation_catalog[pid] = AssistantCitation(
            id=pid,
            source_type="problem",
            title=problem.title,
            excerpt=problem.normalized_statement[:280],
            retro_id=problem.retro_id,
            href_hint=f"/retro/{problem.retro_id}/confirm",
        )
        cluster_title = ""
        if problem.cluster_id and problem.cluster_id in clusters:
            cluster_title = clusters[problem.cluster_id].canonical_title
        context_lines.append(
            f"[{pid}] type=problem cluster={cluster_title or '-'}\n"
            f"title={problem.title}\nstatement={problem.normalized_statement}"
        )

    for cluster in clusters.values():
        kid = f"cluster:{cluster.id}"
        citation_catalog[kid] = AssistantCitation(
            id=kid,
            source_type="cluster",
            title=cluster.canonical_title,
            excerpt=cluster.canonical_title,
            href_hint="/trends",
        )
        context_lines.append(
            f"[{kid}] type=cluster title={cluster.canonical_title} category={cluster.category}"
        )

    for action in actions:
        aid = f"action:{action.id}"
        citation_catalog[aid] = AssistantCitation(
            id=aid,
            source_type="action",
            title=action.title,
            excerpt=f"{action.status} · due {action.due_date.isoformat()} · {action.owner}",
            retro_id=action.retro_id,
            action_id=action.id,
            href_hint="/actions/board",
        )
        context_lines.append(
            f"[{aid}] type=action status={action.status} owner={action.owner} "
            f"due={action.due_date.isoformat()}\n"
            f"title={action.title}\ncriteria={action.success_criteria}"
        )

    messages = [
        {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_assistant_user_prompt(
                question=question,
                context_blocks="\n\n".join(context_lines),
            ),
        },
    ]

    try:
        raw = llm_provider.chat_json(messages)
        result = _LlmAssistantResult.model_validate_json(raw)
    except (llm_provider.LlmError, ValidationError, json.JSONDecodeError) as exc:
        message = getattr(exc, "message", "assistant_llm_failed")
        if isinstance(exc, ValidationError):
            message = "assistant_schema_invalid"
        raise api_error(status.HTTP_502_BAD_GATEWAY, message) from exc

    if result.status not in {"answered", "insufficient_evidence"}:
        result.status = "insufficient_evidence"

    valid_ids: list[str] = []
    seen: set[str] = set()
    for cid in result.citation_ids:
        if cid in citation_catalog and cid not in seen:
            valid_ids.append(cid)
            seen.add(cid)
        if len(valid_ids) >= settings.rag_max_citations:
            break
    if result.status == "answered" and not valid_ids:
        return AssistantQueryResponse(
            status="insufficient_evidence",
            answer="模型没有给出可核对的来源，已拒绝回答。请换个问法，或确认相关复盘已完成分析索引。",
            citations=[],
        )

    citations = [citation_catalog[cid] for cid in valid_ids]
    return AssistantQueryResponse(
        status=result.status,
        answer=result.answer.strip() or "（空回答）",
        citations=citations,
    )
