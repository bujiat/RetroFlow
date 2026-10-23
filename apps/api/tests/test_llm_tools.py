import httpx
import pytest

from app.core.config import settings
from app.providers import llm as llm_provider
from app.providers.llm import LlmError


class _Response:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _Client:
    def __init__(self, handler) -> None:
        self._handler = handler

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def post(self, url: str, headers: dict, json: dict) -> _Response:
        return self._handler(url, headers, json)


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(
        llm_provider.httpx,
        "Client",
        lambda timeout: _Client(handler),
    )


def test_chat_with_tools_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(url: str, headers: dict, json: dict) -> _Response:
        assert "tools" in json
        assert "response_format" not in json
        return _Response(
            200,
            {
                "choices": [{"message": {"content": "  没有需要查的资料。  "}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4},
            },
        )

    _patch_client(monkeypatch, handler)
    result = llm_provider.chat_with_tools(
        [{"role": "user", "content": "你好"}],
        [{"type": "function", "function": {"name": "search"}}],
    )
    assert result.content == "没有需要查的资料。"
    assert result.tool_calls == []
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 4


def test_chat_with_tools_returns_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(url: str, headers: dict, json: dict) -> _Response:
        return _Response(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_retro_content",
                                        "arguments": '{"query": "部署失败"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            },
        )

    _patch_client(monkeypatch, handler)
    result = llm_provider.chat_with_tools([{"role": "user", "content": "部署为什么失败"}], [])
    assert result.content is None
    assert len(result.tool_calls) == 1
    call = result.tool_calls[0]
    assert call.id == "call_1"
    assert call.name == "search_retro_content"
    assert call.arguments == {"query": "部署失败"}
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 8


def test_chat_with_tools_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(url: str, headers: dict, json: dict) -> _Response:
        raise httpx.TimeoutException("slow")

    _patch_client(monkeypatch, handler)
    with pytest.raises(LlmError) as exc:
        llm_provider.chat_with_tools([{"role": "user", "content": "hi"}], [])
    assert exc.value.message == "llm_timeout"


def test_chat_with_tools_bad_tool_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(url: str, headers: dict, json: dict) -> _Response:
        return _Response(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "search_retro_content",
                                        "arguments": "not-json",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    _patch_client(monkeypatch, handler)
    with pytest.raises(LlmError) as exc:
        llm_provider.chat_with_tools([{"role": "user", "content": "hi"}], [])
    assert exc.value.message == "llm_bad_response"
