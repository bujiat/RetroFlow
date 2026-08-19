import json
import re

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


def chat_json(messages: list[dict[str, str]]) -> str:
    if not settings.llm_api_key.strip():
        raise LlmError("llm_not_configured")

    url = _chat_completions_url(settings.llm_base_url)
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

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
        content = data["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise LlmError("llm_bad_response") from exc

    if not isinstance(content, str) or not content.strip():
        raise LlmError("llm_bad_response")

    return extract_json_text(content)
