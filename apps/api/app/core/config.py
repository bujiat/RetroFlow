from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEVELOPMENT_JWT_SECRET = "dev-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    database_url: str = Field(...)

    jwt_secret: str = _DEVELOPMENT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    seed_demo_on_start: bool = True

    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 120.0

    embedding_provider: str = "ollama"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_dim: int = 768
    embedding_timeout_seconds: float = 20.0
    problem_match_threshold: float = 0.75

    rag_retrieval_top_k: int = 10
    rag_context_top_k: int = 5
    rag_min_score: float = 0.32
    rag_max_citations: int = 5

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.app_env.strip().lower() not in {"production", "prod"}:
            return self
        if self.jwt_secret == _DEVELOPMENT_JWT_SECRET or len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters in production")
        origins = self.cors_origin_list
        if not origins or any(not origin.startswith("https://") for origin in origins):
            raise ValueError("CORS_ORIGINS must contain HTTPS origins in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
