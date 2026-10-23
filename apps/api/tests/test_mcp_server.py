import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastmcp.exceptions import ValidationError

from app.agent.tools.actions import ListActionsArgs
from app.agent.tools.base import ToolSpec
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.search import SearchRetroContentArgs
from app.mcp.server import READ_TOOL_NAMES, create_server, run_mcp_tool


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_server_lists_only_the_three_read_tools() -> None:
    server = create_server(user_email="demo@example.com")
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    assert set(tools) == set(READ_TOOL_NAMES)
    for tool in tools.values():
        assert "user_id" not in tool.parameters.get("properties", {})
    focus = tools["list_actions"].parameters["properties"]["focus"]
    assert focus["enum"] == ListActionsArgs.model_json_schema()["properties"]["focus"]["enum"]


def test_missing_email_does_not_open_a_session() -> None:
    def factory() -> FakeSession:
        raise AssertionError("session opened")

    result = run_mcp_tool(
        "search_retro_content",
        {"query": "发布清单"},
        session_factory=factory,
        user_email="  ",
        lookup_user=lambda db, email: None,
    )
    assert result == {
        "ok": False,
        "error": {"code": "mcp_user_not_configured", "message": "未配置 MCP_USER_EMAIL"},
    }


def test_unknown_user_closes_the_session_without_running_the_tool() -> None:
    session = FakeSession()
    called = False

    def handler(db: object, user_id: object, args: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {"hits": []}

    result = run_mcp_tool(
        "search_retro_content",
        {"query": "发布清单"},
        session_factory=lambda: session,
        user_email="missing@example.com",
        lookup_user=lambda db, email: None,
        registry=_search_registry(handler),
    )
    assert result["error"]["code"] == "mcp_user_not_found"
    assert called is False
    assert session.closed is True


def test_search_uses_the_configured_user_not_the_argument() -> None:
    owner = uuid4()
    seen: dict[str, object] = {}
    session = FakeSession()

    def handler(db: object, user_id: object, args: SearchRetroContentArgs) -> dict[str, object]:
        seen["user_id"] = user_id
        seen["query"] = args.query
        return {"hits": [{"id": "chunk:1"}]}

    def lookup(db: object, email: str) -> object | None:
        seen["email"] = email
        return SimpleNamespace(id=owner)

    result = run_mcp_tool(
        "search_retro_content",
        {"query": "发布清单"},
        session_factory=lambda: session,
        user_email="Demo@Example.com",
        lookup_user=lookup,
        registry=_search_registry(handler),
    )
    assert result["ok"] is True
    assert result["data"]["hits"][0]["id"] == "chunk:1"
    assert seen == {"email": "demo@example.com", "user_id": owner, "query": "发布清单"}
    assert session.closed is True


def test_user_id_argument_never_reaches_the_handler() -> None:
    def handler(db: object, user_id: object, args: object) -> dict[str, object]:
        raise AssertionError("handler ran")

    result = run_mcp_tool(
        "search_retro_content",
        {"query": "发布清单", "user_id": str(uuid4())},
        session_factory=lambda: FakeSession(),
        user_email="demo@example.com",
        lookup_user=lambda db, email: SimpleNamespace(id=uuid4()),
        registry=_search_registry(handler),
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_propose_action_is_unknown_and_does_not_open_a_session() -> None:
    def factory() -> FakeSession:
        raise AssertionError("session opened")

    result = run_mcp_tool(
        "propose_action",
        {"problem_id": "problem:1"},
        session_factory=factory,
        user_email="demo@example.com",
        lookup_user=lambda db, email: SimpleNamespace(id=uuid4()),
    )
    assert result["error"]["code"] == "unknown_tool"


def test_fastmcp_rejects_user_id_before_opening_a_session() -> None:
    def factory() -> FakeSession:
        raise AssertionError("session opened")

    server = create_server(session_factory=factory, user_email="demo@example.com")
    with pytest.raises(ValidationError):
        asyncio.run(
            server.call_tool(
                "search_retro_content",
                {"query": "发布清单", "user_id": str(uuid4())},
            )
        )


def test_fastmcp_call_returns_the_configured_users_result() -> None:
    owner = uuid4()
    session = FakeSession()

    def handler(db: object, user_id: object, args: SearchRetroContentArgs) -> dict[str, object]:
        assert user_id == owner
        assert args.query == "发布清单"
        return {"hits": []}

    server = create_server(
        session_factory=lambda: session,
        user_email="demo@example.com",
        lookup_user=lambda db, email: SimpleNamespace(id=owner),
        registry=_search_registry(handler),
    )
    result = asyncio.run(server.call_tool("search_retro_content", {"query": "发布清单"}))
    assert result.is_error is False
    assert result.structured_content == {"ok": True, "data": {"hits": []}}
    assert session.closed is True


def _search_registry(handler: object) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="search_retro_content",
            description="search",
            args_model=SearchRetroContentArgs,
            handler=handler,
        )
    )
    return registry
