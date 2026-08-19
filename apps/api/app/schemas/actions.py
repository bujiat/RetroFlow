from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class PatchActionRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def allowed_patch_status(cls, value: str) -> str:
        if value not in {"open", "in_progress", "cancelled"}:
            raise ValueError("invalid status")
        return value


class SubmitEvidenceRequest(BaseModel):
    completion_note: str = Field(min_length=1, max_length=2000)
    evidence_text: str | None = Field(default=None, max_length=5000)
    evidence_url: str | None = Field(default=None, max_length=2000)

    @field_validator("completion_note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("evidence_text", "evidence_url")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("evidence_url")
    @classmethod
    def http_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("evidence_url must start with http:// or https://")
        return value

    @model_validator(mode="after")
    def require_one_evidence(self) -> "SubmitEvidenceRequest":
        if not self.evidence_text and not self.evidence_url:
            raise ValueError("evidence_text or evidence_url required")
        return self


class RejectActionRequest(BaseModel):
    reject_reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reject_reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ActionItemOut(BaseModel):
    id: UUID
    retro_id: UUID
    problem_occurrence_id: UUID
    title: str
    description: str
    owner: str
    due_date: date
    success_criteria: str
    status: str
    verified_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActionEventOut(BaseModel):
    id: UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    note: str | None
    evidence_text: str | None
    evidence_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MyWeekOut(BaseModel):
    """Buckets for the concise「我的本周」view. Computed on the server."""

    overdue: list[ActionItemOut]
    due_this_week: list[ActionItemOut]
    awaiting_verify: list[ActionItemOut]
