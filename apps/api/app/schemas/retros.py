from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.analysis import AnalysisSummary

RetroType = Literal["sprint", "incident", "release"]


class CreateRetroRequest(BaseModel):
    type: RetroType
    title: str = Field(min_length=1, max_length=200)
    review_date: date
    raw_content: str = Field(min_length=1, max_length=200_000)

    @field_validator("title", "raw_content")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class RetroListItem(BaseModel):
    id: UUID
    type: RetroType
    title: str
    review_date: date
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ActionDraftOut(BaseModel):
    id: UUID
    title: str
    description: str
    suggested_success_criteria: str

    model_config = {"from_attributes": True}


class ProblemOut(BaseModel):
    id: UUID
    title: str
    normalized_statement: str
    category: str
    severity: str
    source_quote: str
    disposition: str
    match_status: str
    cluster_id: UUID | None = None
    cluster_title: str | None = None
    suggested_actions: list[ActionDraftOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RetroDetail(RetroListItem):
    raw_content: str
    index_status: str
    analysis_error: str | None = None
    analysis_summary: AnalysisSummary | None = None
    updated_at: datetime
    problems: list[ProblemOut] = Field(default_factory=list)

    @classmethod
    def from_parts(
        cls,
        *,
        retro: Any,
        problems: list[Any],
        drafts: list[Any],
        clusters_by_id: dict[UUID, Any] | None = None,
    ) -> "RetroDetail":
        drafts_by_problem: dict[UUID, list[ActionDraftOut]] = {}
        for draft in drafts:
            drafts_by_problem.setdefault(draft.problem_occurrence_id, []).append(
                ActionDraftOut.model_validate(draft)
            )

        cluster_map = clusters_by_id or {}
        problem_outs = [
            ProblemOut(
                id=problem.id,
                title=problem.title,
                normalized_statement=problem.normalized_statement,
                category=problem.category,
                severity=problem.severity,
                source_quote=problem.source_quote,
                disposition=problem.disposition,
                match_status=problem.match_status,
                cluster_id=problem.cluster_id,
                cluster_title=(
                    cluster_map[problem.cluster_id].canonical_title
                    if problem.cluster_id and problem.cluster_id in cluster_map
                    else None
                ),
                suggested_actions=drafts_by_problem.get(problem.id, []),
            )
            for problem in problems
        ]

        summary = None
        if retro.analysis_summary is not None:
            summary = AnalysisSummary.model_validate(retro.analysis_summary)

        return cls(
            id=retro.id,
            type=retro.type,
            title=retro.title,
            review_date=retro.review_date,
            status=retro.status,
            created_at=retro.created_at,
            raw_content=retro.raw_content,
            index_status=retro.index_status,
            analysis_error=retro.analysis_error,
            analysis_summary=summary,
            updated_at=retro.updated_at,
            problems=problem_outs,
        )


class PublishActionInput(BaseModel):
    action_draft_id: UUID
    owner: str = Field(min_length=1, max_length=320)
    due_date: date
    success_criteria: str = Field(min_length=1, max_length=2000)

    @field_validator("owner", "success_criteria")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class PublishRetroRequest(BaseModel):
    discarded_problem_ids: list[UUID] = Field(default_factory=list)
    discarded_action_draft_ids: list[UUID] = Field(default_factory=list)
    actions: list[PublishActionInput] = Field(min_length=1, max_length=3)


