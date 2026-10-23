import json
import re
from dataclasses import dataclass

import httpx

from app.core.config import settings

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


class LlmError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def extract_json_text(content: str) -> str:
    text = content.strip()
    text = _FENCE_RE.sub("", text).strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class ChatWithToolsResult:
    content: str | None
    tool_calls: list[ToolCall]
    prompt_tokens: int
    completion_tokens: int


def _post_chat(payload: dict[str, object]) -> dict[str, object]:
    if not settings.llm_api_key.strip():
        raise LlmError("llm_not_configured")

    url = _chat_completions_url(settings.llm_base_url)
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise LlmError("llm_timeout") from exc
    except httpx.HTTPError as exc:
        raise LlmError("llm_request_failed") from exc

    if response.status_code >= 400:
        raise LlmError("llm_request_failed")

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise LlmError("llm_bad_response") from exc
    if not isinstance(data, dict):
        raise LlmError("llm_bad_response")
    return data


def chat_json(messages: list[dict[str, str]]) -> str:
    data = _post_chat(
        {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
    )
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError("llm_bad_response") from exc
    if not isinstance(content, str) or not content.strip():
        raise LlmError("llm_bad_response")
    return extract_json_text(content)


def chat_with_tools(
    messages: list[dict[str, object]],
    tools: list[dict[str, object]],
) -> ChatWithToolsResult:
    """Ask the model for a final answer or a list of tool calls. Does not run tools."""
    data = _post_chat(
        {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
            "tools": tools,
        }
    )
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError("llm_bad_response") from exc
    if not isinstance(message, dict):
        raise LlmError("llm_bad_response")

    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    prompt_tokens = _usage_count(usage, "prompt_tokens")
    completion_tokens = _usage_count(usage, "completion_tokens")
    tool_calls = _parse_tool_calls(message.get("tool_calls"))
    content = message.get("content")
    text = content.strip() if isinstance(content, str) and content.strip() else None
    if not tool_calls and text is None:
        raise LlmError("llm_bad_response")
    return ChatWithToolsResult(
        content=text,
        tool_calls=tool_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def _usage_count(usage: object, key: str) -> int:
    if not isinstance(usage, dict):
        return 0
    value = usage.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _parse_tool_calls(raw: object) -> list[ToolCall]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise LlmError("llm_bad_response")
    calls: list[ToolCall] = []
    for item in raw:
        if not isinstance(item, dict):
            raise LlmError("llm_bad_response")
        function = item.get("function")
        if not isinstance(function, dict):
            raise LlmError("llm_bad_response")
        call_id = item.get("id")
        name = function.get("name")
        arguments_raw = function.get("arguments", "{}")
        if not isinstance(call_id, str) or not call_id.strip():
            raise LlmError("llm_bad_response")
        if not isinstance(name, str) or not name.strip():
            raise LlmError("llm_bad_response")
        if not isinstance(arguments_raw, str):
            raise LlmError("llm_bad_response")
        try:
            arguments = json.loads(arguments_raw) if arguments_raw.strip() else {}
        except json.JSONDecodeError as exc:
            raise LlmError("llm_bad_response") from exc
        if not isinstance(arguments, dict):
            raise LlmError("llm_bad_response")
        calls.append(ToolCall(id=call_id, name=name, arguments=arguments))
    return calls
