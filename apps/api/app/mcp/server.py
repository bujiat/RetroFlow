"""Read-only MCP tools for Cursor.

The signed-in RetroFlow user is MCP_USER_EMAIL on this process.
Tool arguments do not include user_id. Propose and verify tools are not registered.
"""

from collections.abc import Callable
from typing import Literal

from fastmcp import FastMCP
from sqlalchemy.orm import Session

from app.agent.tools.executor import execute_tool
from app.agent.tools.registry import ToolRegistry, default_registry
from app.core.config import settings
from app.core.db import SessionLocal
from app.repositories.users import get_user_by_email

READ_TOOL_NAMES = ("search_retro_content", "list_actions", "get_trends")

SessionFactory = Callable[[], Session]
UserLookup = Callable[[Session, str], object | None]


def build_mcp_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for name in READ_TOOL_NAMES:
        tool = default_registry.get(name)
        if tool is None:
            raise RuntimeError(f"missing tool {name}")
        registry.register(tool)
    return registry


def run_mcp_tool(
    name: str,
    arguments: dict[str, object],
    *,
    session_factory: SessionFactory,
    user_email: str,
    lookup_user: UserLookup,
    registry: ToolRegistry | None = None,
) -> dict[str, object]:
    tools = registry or build_mcp_registry()
    if tools.get(name) is None:
        return _error("unknown_tool", f"未知工具：{name}")
    email = user_email.strip().lower()
    if not email:
        return _error("mcp_user_not_configured", "未配置 MCP_USER_EMAIL")
    db = session_factory()
    try:
        user = lookup_user(db, email)
        if user is None or getattr(user, "id", None) is None:
            return _error("mcp_user_not_found", "MCP_USER_EMAIL 对应用户不存在")
        return execute_tool(
            db,
            user_id=user.id,
            name=name,
            arguments=arguments,
            registry=tools,
        )
    except Exception:
        return _error("tool_failed", "工具执行失败")
    finally:
        db.close()


def create_server(
    *,
    session_factory: SessionFactory = SessionLocal,
    user_email: str | None = None,
    lookup_user: UserLookup = get_user_by_email,
    registry: ToolRegistry | None = None,
) -> FastMCP:
    email = settings.mcp_user_email if user_email is None else user_email
    tools = registry or build_mcp_registry()
    mcp = FastMCP("retroflow")

    def _run(name: str, arguments: dict[str, object]) -> dict[str, object]:
        return run_mcp_tool(
            name,
            arguments,
            session_factory=session_factory,
            user_email=email,
            lookup_user=lookup_user,
            registry=tools,
        )

    search = default_registry.get("search_retro_content")
    actions = default_registry.get("list_actions")
    trends = default_registry.get("get_trends")
    if search is None or actions is None or trends is None:
        raise RuntimeError("missing read tool")

    @mcp.tool(name="search_retro_content", description=search.description)
    def search_retro_content(query: str) -> dict[str, object]:
        return _run("search_retro_content", {"query": query})

    @mcp.tool(name="list_actions", description=actions.description)
    def list_actions(
        focus: Literal["open_work", "overdue", "due_this_week", "awaiting_verify", "all"] = "open_work",
    ) -> dict[str, object]:
        return _run("list_actions", {"focus": focus})

    @mcp.tool(name="get_trends", description=trends.description)
    def get_trends() -> dict[str, object]:
        return _run("get_trends", {})

    return mcp


def _error(code: str, message: str) -> dict[str, object]:
    return {"ok": False, "error": {"code": code, "message": message}}
