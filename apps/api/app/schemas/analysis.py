from typing import Literal

from pydantic import BaseModel, Field, field_validator

ProblemCategory = Literal[
    "process",
    "quality",
    "delivery",
    "collaboration",
    "reliability",
    "tooling",
    "other",
]
ProblemSeverity = Literal["low", "medium", "high"]


class SuggestedActionDraft(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=5000)
    suggested_success_criteria: str = Field(min_length=1, max_length=2000)

    @field_validator("title", "description", "suggested_success_criteria")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class AnalysisProblem(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    normalized_statement: str = Field(min_length=1, max_length=2000)
    category: ProblemCategory
    severity: ProblemSeverity
    source_quote: str = Field(min_length=1, max_length=5000)
    suggested_actions: list[SuggestedActionDraft] = Field(min_length=1, max_length=3)

    @field_validator("title", "normalized_statement", "source_quote")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class AnalysisDecision(BaseModel):
    decision: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=2000)


class AnalysisRisk(BaseModel):
    risk: str = Field(min_length=1, max_length=1000)
    suggestion: str = Field(min_length=1, max_length=2000)


class AnalysisSummary(BaseModel):
    keep: list[str] = Field(default_factory=list, max_length=10)
    decisions: list[AnalysisDecision] = Field(default_factory=list, max_length=10)
    risks: list[AnalysisRisk] = Field(default_factory=list, max_length=10)


class LlmAnalysisResult(BaseModel):
    summary: AnalysisSummary
    problems: list[AnalysisProblem] = Field(default_factory=list, max_length=5)
