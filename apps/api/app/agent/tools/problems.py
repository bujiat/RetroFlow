from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolSpec
from app.core.config import settings
from app.providers import embedding as embedding_provider
from app.repositories import clusters as clusters_repo


class FindSimilarProblemsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=2,
        max_length=500,
        description="要对照历史重复问题的描述，用用户说的问题原话即可。",
    )


def execute_find_similar_problems(
    db: Session,
    user_id: UUID,
    args: FindSimilarProblemsArgs,
) -> dict[str, object]:
    vector = embedding_provider.embed_texts([args.query])[0]
    nearest = clusters_repo.find_nearest_cluster(db, user_id=user_id, vector=vector)
    threshold = settings.problem_match_threshold
    if nearest is None or nearest[1] < threshold:
        return {"threshold": threshold, "match": None}
    cluster, score = nearest
    return {
        "threshold": threshold,
        "match": {
            "id": f"cluster:{cluster.id}",
            "title": cluster.canonical_title,
            "category": cluster.category,
            "score": round(float(score), 3),
        },
    }


find_similar_problems_tool = ToolSpec(
    name="find_similar_problems",
    description=(
        "判断一个问题是否属于当前用户历史上已经出现过的重复问题。"
        "用户问「这个问题以前出现过吗」时使用。"
        "相似度低于系统阈值时 match 为 null。"
    ),
    args_model=FindSimilarProblemsArgs,
    handler=execute_find_similar_problems,
)
