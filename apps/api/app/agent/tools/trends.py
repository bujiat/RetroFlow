from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolSpec
from app.agent.tools.users import load_user
from app.services import trends as trends_service


class GetTrendsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def execute_get_trends(
    db: Session,
    user_id: UUID,
    args: GetTrendsArgs,
) -> dict[str, object]:
    user = load_user(db, user_id)
    if user is None:
        return {"found": False}
    summary = trends_service.get_summary(db, user).model_dump(mode="json")
    for cluster in summary["top_clusters"]:
        cluster["id"] = f"cluster:{cluster['id']}"
    for item in summary["overdue_items"]:
        item["id"] = f"action:{item['id']}"
    summary["found"] = True
    return summary


get_trends_tool = ToolSpec(
    name="get_trends",
    description=(
        "查看当前用户的改进趋势：逾期数量、待验收数量、验收率、重复问题。"
        "不用于回答某一次会议的原文细节。"
    ),
    args_model=GetTrendsArgs,
    handler=execute_get_trends,
)
