from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.actions import ActionItemOut
from app.schemas.assistant import AssistantCitation


class AgentChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class PendingOperationBrief(BaseModel):
    id: UUID
    tool_name: str
    summary: str
    expires_at: datetime


class AgentChatResponse(BaseModel):
    status: Literal["answered", "insufficient_evidence", "max_steps", "tool_failures"]
    answer: str
    citations: list[AssistantCitation] = Field(default_factory=list)
    pending_operations: list[PendingOperationBrief] = Field(default_factory=list)
    run_id: UUID | None = None


class ConfirmOperationResponse(BaseModel):
    operation: PendingOperationBrief
    action: ActionItemOut


class AgentRunSummary(BaseModel):
    id: UUID
    kind: str
    status: str
    question: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    created_at: datetime


class AgentRunList(BaseModel):
    items: list[AgentRunSummary]
    limited: bool


class AgentStepOut(BaseModel):
    step_index: int
    step_type: str
    tool_name: str | None
    arguments: dict | None
    result_summary: str | None
    error: str | None
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int


class AgentRunDetail(AgentRunSummary):
    output: str | None
    steps: list[AgentStepOut]
