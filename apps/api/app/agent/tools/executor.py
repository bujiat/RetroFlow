import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.tools.registry import ToolRegistry, default_registry
from app.providers import embedding as embedding_provider
from app.providers.github import GithubError

MAX_TOOL_RESULT_CHARS = 4000


def execute_tool(
    db: Session,
    *,
    user_id: UUID,
    name: str,
    arguments: object,
    registry: ToolRegistry | None = None,
) -> dict[str, object]:
    """Validate arguments, inject user_id, and return a structured result. Never raises."""
    tools = registry or default_registry
    tool = tools.get(name)
    if tool is None:
        return _error("unknown_tool", f"未知工具：{name}")
    if not isinstance(arguments, dict):
        return _error("invalid_arguments", "参数必须是对象")
    try:
        args = tool.args_model.model_validate(arguments)
    except ValidationError as exc:
        return _error("invalid_arguments", "参数不符合工具定义", _error_details(exc))
    try:
        data = tool.handler(db, user_id, args)
    except embedding_provider.EmbeddingError as exc:
        return _error("tool_failed", exc.message)
    except GithubError as exc:
        return _error(exc.code, exc.message)
    except Exception:
        return _error("tool_failed", "工具执行失败")
    return {"ok": True, "data": _truncate(data)}


def _error(
    code: str,
    message: str,
    details: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    error: dict[str, object] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"ok": False, "error": error}


def _error_details(exc: ValidationError) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for item in exc.errors()[:5]:
        details.append(
            {
                "loc": [str(part) for part in item.get("loc", ())],
                "msg": str(item.get("msg", "")),
            }
        )
    return details


def _truncate(data: dict[str, object]) -> dict[str, object]:
    encoded = json.dumps(data, ensure_ascii=False)
    if len(encoded) <= MAX_TOOL_RESULT_CHARS:
        return data
    return {"truncated": True, "preview": encoded[:MAX_TOOL_RESULT_CHARS]}
