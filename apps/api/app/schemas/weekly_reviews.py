from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WeeklyReviewCitation(BaseModel):
    id: str
    source_type: Literal["action", "event", "retro", "cluster"]
    title: str
    excerpt: str
    retro_id: UUID | None = None
    action_id: UUID | None = None
    href_hint: str | None = None


class GenerateWeeklyReviewRequest(BaseModel):
    week_start: date | None = None


class WeeklyReviewOut(BaseModel):
    """Draft or saved weekly review shown to the client."""

    week_start: date
    week_end: date
    status: Literal["ok", "empty", "insufficient_evidence"]
    content_markdown: str
    citations: list[WeeklyReviewCitation] = Field(default_factory=list)
    saved: bool = False


class SaveWeeklyReviewRequest(BaseModel):
    content_markdown: str = Field(min_length=1, max_length=20000)
    citation_ids: list[str] = Field(min_length=1, max_length=8)
