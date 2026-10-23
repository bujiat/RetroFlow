from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolSpec
from app.retrieval.search import retrieve_chunks


class SearchRetroContentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=2,
        max_length=500,
        description="要在当前用户的复盘原文里查找的问题，用用户的原话即可。",
    )


def execute_search_retro_content(
    db: Session,
    user_id: UUID,
    args: SearchRetroContentArgs,
) -> dict[str, object]:
    scored = retrieve_chunks(db, user_id=user_id, query=args.query)
    hits = [
        {
            "id": f"chunk:{chunk.id}",
            "retro_id": str(chunk.retro_id),
            "score": round(float(score), 3),
            "excerpt": chunk.content[:280],
        }
        for chunk, score in scored
    ]
    return {"hits": hits}


search_retro_content_tool = ToolSpec(
    name="search_retro_content",
    description=(
        "在当前用户自己的复盘原文里按语义和关键词搜索相关片段。"
        "用户询问某次复盘、会议里说过什么，或提到部署、回滚这类原词时使用。"
    ),
    args_model=SearchRetroContentArgs,
    handler=execute_search_retro_content,
)
