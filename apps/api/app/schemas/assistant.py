from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AssistantQueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class AssistantCitation(BaseModel):
    id: str
    source_type: Literal["action", "cluster", "chunk", "problem"]
    title: str
    excerpt: str
    retro_id: UUID | None = None
    action_id: UUID | None = None
    href_hint: str | None = None


class AssistantQueryResponse(BaseModel):
    status: Literal["answered", "insufficient_evidence"]
    answer: str
    citations: list[AssistantCitation] = Field(default_factory=list)
