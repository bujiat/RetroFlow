from datetime import date
from uuid import UUID

from pydantic import BaseModel


class OverdueActionBrief(BaseModel):
    id: UUID
    title: str
    owner: str
    due_date: date
    status: str


class ClusterTrendBrief(BaseModel):
    id: UUID
    title: str
    occurrence_count: int


class TrendsSummary(BaseModel):
    overdue_actions: int
    awaiting_work: int
    awaiting_verify: int
    verified_actions: int
    cancelled_actions: int
    verification_rate: float | None
    kept_problems: int
    published_retros: int
    recurring_clusters: int
    top_clusters: list[ClusterTrendBrief]
    overdue_items: list[OverdueActionBrief]
