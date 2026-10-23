from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolSpec
from app.agent.tools.executor import MAX_TOOL_RESULT_CHARS, execute_tool
from app.agent.tools.registry import ToolRegistry, default_registry
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.content_chunk import ContentChunk
from app.models.retro import Retro
from app.models.user import User
from app.providers.embedding import EmbeddingError


def test_schema_has_query_and_not_user_id() -> None:
    tools = {
        tool["function"]["name"]: tool["function"]
        for tool in default_registry.openai_tools()
    }
    assert set(tools) == {
        "search_retro_content",
        "find_similar_problems",
        "list_actions",
        "get_action_history",
        "get_trends",
        "read_github_pr",
        "propose_action",
        "propose_status_change",
    }
    for function in tools.values():
        assert "user_id" not in function["parameters"]["properties"]
    assert "query" in tools["search_retro_content"]["parameters"]["properties"]
    assert "query" in tools["find_similar_problems"]["parameters"]["properties"]
    assert "action_id" in tools["get_action_history"]["parameters"]["properties"]


def test_invalid_arguments_reject_user_id() -> None:
    result = execute_tool(
        _unused_db(),
        user_id=uuid4(),
        name="search_retro_content",
        arguments={"query": "部署失败", "user_id": str(uuid4())},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_unknown_tool() -> None:
    result = execute_tool(
        _unused_db(),
        user_id=uuid4(),
        name="drop_database",
        arguments={},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "unknown_tool"


def test_embedding_failure_is_structured(monkeypatch) -> None:
    def fail(_texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("embedding_timeout")

    monkeypatch.setattr("app.retrieval.search.embedding_provider.embed_texts", fail)
    result = execute_tool(
        _unused_db(),
        user_id=uuid4(),
        name="search_retro_content",
        arguments={"query": "部署失败"},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "tool_failed"
    assert result["error"]["message"] == "embedding_timeout"


def test_handler_exception_is_structured() -> None:
    def boom(_db: Session, _user_id: UUID, _args: BaseModel) -> dict[str, object]:
        raise RuntimeError("secret traceback")

    class EmptyArgs(BaseModel):
        model_config = ConfigDict(extra="forbid")
        query: str = Field(min_length=1)

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="boom",
            description="test",
            args_model=EmptyArgs,
            handler=boom,
        )
    )
    result = execute_tool(
        _unused_db(),
        user_id=uuid4(),
        name="boom",
        arguments={"query": "x"},
        registry=registry,
    )
    assert result == {"ok": False, "error": {"code": "tool_failed", "message": "工具执行失败"}}


def test_long_result_is_truncated() -> None:
    def huge(_db: Session, _user_id: UUID, _args: BaseModel) -> dict[str, object]:
        return {"blob": "x" * (MAX_TOOL_RESULT_CHARS + 50)}

    class EmptyArgs(BaseModel):
        model_config = ConfigDict(extra="forbid")

    registry = ToolRegistry()
    registry.register(
        ToolSpec(name="huge", description="test", args_model=EmptyArgs, handler=huge)
    )
    result = execute_tool(
        _unused_db(),
        user_id=uuid4(),
        name="huge",
        arguments={},
        registry=registry,
    )
    assert result["ok"] is True
    data = result["data"]
    assert data["truncated"] is True
    assert len(data["preview"]) == MAX_TOOL_RESULT_CHARS


def test_search_passes_injected_user_id(monkeypatch) -> None:
    user_id = uuid4()
    seen: dict[str, UUID] = {}

    def fake_embed(_texts: list[str]) -> list[list[float]]:
        return [[0.1] * settings.embedding_dim]

    def fake_search(db: Session, *, user_id: UUID, vector: list[float], limit: int):
        seen["user_id"] = user_id
        chunk = SimpleNamespace(id=uuid4(), retro_id=uuid4(), content="部署失败是因为配置写错")
        return [(chunk, 0.91)]

    monkeypatch.setattr("app.retrieval.search.embedding_provider.embed_texts", fake_embed)
    monkeypatch.setattr("app.retrieval.search.chunks_repo.search_chunks", fake_search)
    monkeypatch.setattr(
        "app.retrieval.search.chunks_repo.list_chunks_for_user",
        lambda db, *, user_id: [],
    )
    result = execute_tool(
        _unused_db(),
        user_id=user_id,
        name="search_retro_content",
        arguments={"query": "部署失败"},
    )
    assert seen["user_id"] == user_id
    assert result["ok"] is True
    assert result["data"]["hits"][0]["excerpt"] == "部署失败是因为配置写错"


def test_search_cannot_see_other_users_chunks(monkeypatch) -> None:
    _require_postgres()
    user_a_id = uuid4()
    user_b_id = uuid4()
    retro_a_id = uuid4()
    retro_b_id = uuid4()
    vector = [1.0] + [0.0] * (settings.embedding_dim - 1)
    monkeypatch.setattr(
        "app.retrieval.search.embedding_provider.embed_texts",
        lambda _texts: [vector],
    )
    db = SessionLocal()
    try:
        db.add(_user(user_a_id, "agent-a"))
        db.add(_user(user_b_id, "agent-b"))
        db.flush()
        db.add(_retro(retro_a_id, user_a_id, "user A only"))
        db.add(_retro(retro_b_id, user_b_id, "user B only"))
        db.flush()
        db.add(_chunk(user_a_id, retro_a_id, "only-user-a-secret", vector))
        db.add(_chunk(user_b_id, retro_b_id, "only-user-b-secret", vector))
        db.commit()
        result = execute_tool(
            db,
            user_id=user_a_id,
            name="search_retro_content",
            arguments={"query": "部署失败"},
        )
    finally:
        db.rollback()
        db.execute(delete(User).where(User.id.in_([user_a_id, user_b_id])))
        db.commit()
        db.close()

    excerpts = [hit["excerpt"] for hit in result["data"]["hits"]]
    assert "only-user-a-secret" in excerpts
    assert "only-user-b-secret" not in excerpts


def _unused_db() -> Session:
    return None  # type: ignore[return-value]


def _require_postgres() -> None:
    url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        pytest.skip(f"PostgreSQL not running: {exc}")


def _user(user_id: UUID, prefix: str) -> User:
    return User(
        id=user_id,
        email=f"{prefix}-{user_id.hex[:8]}@example.com",
        password_hash="x",
        locale="zh-CN",
    )


def _retro(retro_id: UUID, user_id: UUID, raw_content: str) -> Retro:
    return Retro(
        id=retro_id,
        user_id=user_id,
        type="sprint",
        title="retro",
        review_date=date(2026, 8, 17),
        raw_content=raw_content,
        status="draft",
        index_status="pending",
    )


def _chunk(user_id: UUID, retro_id: UUID, content: str, vector: list[float]) -> ContentChunk:
    return ContentChunk(
        id=uuid4(),
        user_id=user_id,
        retro_id=retro_id,
        chunk_index=0,
        content=content,
        start_offset=0,
        end_offset=len(content),
        embedding=vector,
    )
