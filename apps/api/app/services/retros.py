from uuid import UUID

from fastapi import status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models.retro import Retro
from app.models.user import User
from app.providers import embedding as embedding_provider
from app.providers import llm as llm_provider
from app.providers.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    build_analysis_user_prompt,
    build_repair_user_prompt,
)
from app.repositories import actions as actions_repo
from app.repositories import analysis as analysis_repo
from app.repositories import clusters as clusters_repo
from app.repositories import retros as retros_repo
from app.schemas.analysis import LlmAnalysisResult
from app.schemas.retros import (
    CreateRetroRequest,
    PublishRetroRequest,
    RetroDetail,
    RetroListItem,
)
from app.services import indexing as indexing_service

# analyzing 也可重入：进程中断时可能卡在 analyzing，需能重试
ANALYZABLE_STATUSES = {"draft", "analyzing", "analysis_failed", "ready_for_review"}


def list_retros(db: Session, user: User) -> list[RetroListItem]:
    rows = retros_repo.list_retros_for_user(db, user.id)
    return [RetroListItem.model_validate(row) for row in rows]


def get_retro(db: Session, user: User, retro_id: UUID) -> RetroDetail:
    row = retros_repo.get_retro_for_user(db, user_id=user.id, retro_id=retro_id)
    if row is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "retro_not_found")
    return _detail(db, user.id, row)


def create_retro(db: Session, user: User, payload: CreateRetroRequest) -> RetroListItem:
    row = retros_repo.create_retro(
        db,
        user_id=user.id,
        type=payload.type,
        title=payload.title,
        review_date=payload.review_date,
        raw_content=payload.raw_content,
    )
    return RetroListItem.model_validate(row)


def analyze_retro(db: Session, user: User, retro_id: UUID) -> RetroDetail:
    retro = retros_repo.get_retro_for_user(db, user_id=user.id, retro_id=retro_id)
    if retro is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "retro_not_found")
    if retro.status == "published":
        raise api_error(status.HTTP_409_CONFLICT, "retro_already_published")
    if retro.status not in ANALYZABLE_STATUSES:
        raise api_error(status.HTTP_409_CONFLICT, "retro_not_analyzable")

    retro.status = "analyzing"
    retro.analysis_error = None
    db.commit()

    user_prompt = build_analysis_user_prompt(
        retro_type=retro.type,
        title=retro.title,
        review_date=retro.review_date.isoformat(),
        raw_content=retro.raw_content,
    )
    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        analysis = _run_llm_analysis(messages)
        problems, _drafts = analysis_repo.replace_analysis_results(
            db,
            user_id=user.id,
            retro_id=retro.id,
            analysis=analysis,
        )
        clusters_repo.assign_clusters_for_problems(
            db,
            user_id=user.id,
            problems=problems,
        )
        # RAG index: failure must not undo analysis — only mark index_status.
        indexing_service.index_retro_content(db, user_id=user.id, retro=retro)
        retro.status = "ready_for_review"
        retro.analysis_error = None
        retro.analysis_summary = analysis.summary.model_dump()
        db.commit()
        db.refresh(retro)
        return _detail(db, user.id, retro)
    except llm_provider.LlmError as exc:
        db.rollback()
        _mark_failed(db, retro, exc.message)
        raise api_error(status.HTTP_502_BAD_GATEWAY, exc.message) from exc
    except embedding_provider.EmbeddingError as exc:
        db.rollback()
        _mark_failed(db, retro, exc.message)
        raise api_error(status.HTTP_502_BAD_GATEWAY, exc.message) from exc
    except ValidationError as exc:
        db.rollback()
        _mark_failed(db, retro, "analysis_schema_invalid")
        raise api_error(status.HTTP_502_BAD_GATEWAY, "analysis_schema_invalid") from exc
    except Exception as exc:
        db.rollback()
        _mark_failed(db, retro, "analysis_persist_failed")
        raise api_error(
            status.HTTP_502_BAD_GATEWAY,
            "analysis_persist_failed",
        ) from exc


def publish_retro(
    db: Session,
    user: User,
    retro_id: UUID,
    payload: PublishRetroRequest,
) -> RetroDetail:
    retro = retros_repo.get_retro_for_user(
        db,
        user_id=user.id,
        retro_id=retro_id,
        for_update=True,
    )
    if retro is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "retro_not_found")
    if retro.status == "published":
        raise api_error(status.HTTP_409_CONFLICT, "retro_already_published")
    if retro.status != "ready_for_review":
        raise api_error(status.HTTP_409_CONFLICT, "retro_not_ready_to_publish")

    all_problems = analysis_repo.list_problems_for_retro(
        db,
        user_id=user.id,
        retro_id=retro.id,
    )
    problems_by_id = {p.id: p for p in all_problems}

    discarded_ids = set(payload.discarded_problem_ids)
    for pid in discarded_ids:
        if pid not in problems_by_id:
            raise api_error(status.HTTP_400_BAD_REQUEST, "invalid_discarded_problem")

    kept_problems = [p for p in all_problems if p.id not in discarded_ids]
    if len(kept_problems) > 5:
        raise api_error(status.HTTP_400_BAD_REQUEST, "too_many_problems")

    discarded_action_ids = set(payload.discarded_action_draft_ids)
    action_ids = [a.action_draft_id for a in payload.actions]
    if len(action_ids) != len(set(action_ids)):
        raise api_error(status.HTTP_400_BAD_REQUEST, "duplicate_action_draft")
    if any(aid in discarded_action_ids for aid in action_ids):
        raise api_error(status.HTTP_400_BAD_REQUEST, "action_marked_discarded")

    drafts = actions_repo.get_drafts_by_ids(
        db,
        user_id=user.id,
        retro_id=retro.id,
        draft_ids=action_ids,
    )
    drafts_by_id = {d.id: d for d in drafts}
    if len(drafts_by_id) != len(action_ids):
        raise api_error(status.HTTP_400_BAD_REQUEST, "invalid_action_draft")

    for draft in drafts:
        if draft.problem_occurrence_id in discarded_ids:
            raise api_error(status.HTTP_400_BAD_REQUEST, "action_on_discarded_problem")
        problem = problems_by_id.get(draft.problem_occurrence_id)
        if problem is None:
            raise api_error(status.HTTP_400_BAD_REQUEST, "invalid_action_draft")

    to_discard = [problems_by_id[pid] for pid in discarded_ids]
    actions_repo.mark_problems_discarded(db, to_discard)
    actions_repo.create_action_items_from_drafts(
        db,
        user_id=user.id,
        retro_id=retro.id,
        drafts_by_id=drafts_by_id,
        actions=payload.actions,
    )
    retro.status = "published"
    db.commit()
    db.refresh(retro)
    return _detail(db, user.id, retro)


def _run_llm_analysis(messages: list[dict[str, str]]) -> LlmAnalysisResult:
    raw = llm_provider.chat_json(messages)
    try:
        return LlmAnalysisResult.model_validate_json(raw)
    except ValidationError as first_error:
        repair_messages = [
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
        repaired = llm_provider.chat_json(repair_messages)
        try:
            return LlmAnalysisResult.model_validate_json(repaired)
        except ValidationError as second_error:
            raise second_error from first_error


def _mark_failed(db: Session, retro: Retro, code: str) -> None:
    retro.status = "analysis_failed"
    retro.analysis_error = code
    db.commit()


def _detail(db: Session, user_id: UUID, retro: Retro) -> RetroDetail:
    problems = analysis_repo.list_problems_for_retro(
        db,
        user_id=user_id,
        retro_id=retro.id,
    )
    drafts = analysis_repo.list_action_drafts_for_retro(
        db,
        user_id=user_id,
        retro_id=retro.id,
    )
    cluster_ids = [p.cluster_id for p in problems if p.cluster_id is not None]
    clusters = clusters_repo.clusters_by_ids(
        db,
        user_id=user_id,
        cluster_ids=cluster_ids,
    )
    return RetroDetail.from_parts(
        retro=retro,
        problems=problems,
        drafts=drafts,
        clusters_by_id=clusters,
    )
