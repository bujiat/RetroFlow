"""OpenAI-compatible embeddings (Ollama / OpenAI / SiliconFlow).

EMBEDDING_PROVIDER picks defaults; EMBEDDING_BASE_URL / MODEL / API_KEY override them.
"""

from __future__ import annotations

from openai import APIError, APITimeoutError, OpenAI

from app.core.config import settings

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "ollama": {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "nomic-embed-text",
        "api_key": "ollama",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "text-embedding-3-small",
        "api_key": "",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "BAAI/bge-m3",
        "api_key": "",
    },
}


class EmbeddingError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _provider_name() -> str:
    return settings.embedding_provider.strip().lower()


def _defaults() -> dict[str, str]:
    return _PROVIDER_DEFAULTS.get(_provider_name(), {})


def resolved_base_url() -> str:
    return (settings.embedding_base_url.strip() or _defaults().get("base_url", "")).rstrip(
        "/"
    )


def resolved_model() -> str:
    return settings.embedding_model.strip() or _defaults().get("model", "")


def resolved_api_key() -> str:
    if settings.embedding_api_key.strip():
        return settings.embedding_api_key.strip()
    return _defaults().get("api_key", "")


def is_configured() -> bool:
    return bool(
        _provider_name() and resolved_base_url() and resolved_model() and resolved_api_key()
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not is_configured():
        raise EmbeddingError("embedding_not_configured")

    try:
        response = OpenAI(
            api_key=resolved_api_key(),
            base_url=resolved_base_url(),
            timeout=settings.embedding_timeout_seconds,
        ).embeddings.create(
            model=resolved_model(),
            input=texts,
        )
    except APITimeoutError as exc:
        raise EmbeddingError("embedding_timeout") from exc
    except APIError as exc:
        raise EmbeddingError("embedding_request_failed") from exc

    rows = sorted(response.data, key=lambda row: row.index)
    vectors = [list(row.embedding) for row in rows]
    if len(vectors) != len(texts):
        raise EmbeddingError("embedding_bad_response")
    return vectors
