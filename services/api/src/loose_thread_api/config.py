from functools import lru_cache

from pydantic import (
    AliasChoices,
    Field,
    HttpUrl,
    SecretStr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = "development"
    log_level: str = "INFO"
    port: int = 8000
    cors_origins: str = ""
    database_url: SecretStr | None = None
    supabase_url: HttpUrl | None = None
    supabase_anon_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY"),
    )
    openai_api_key: SecretStr | None = None
    openai_model_interpreter: str = "gpt-5.4-mini"
    openai_model_continuity: str = "gpt-5.4-mini"
    openai_model_resumption: str = "gpt-5.4-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    continuity_candidate_limit: int = 8
    retrieval_minimum_score: float = 0.42
    retrieval_weight_rediscovery: float = 0.22
    retrieval_weight_capacity: float = 0.20
    retrieval_weight_context: float = 0.14
    retrieval_weight_open_loop: float = 0.14
    retrieval_weight_thread_momentum: float = 0.10
    retrieval_weight_kind_affinity: float = 0.08
    retrieval_weight_temporal: float = 0.07
    retrieval_weight_novelty: float = 0.05
    job_poll_seconds: float = 1.0
    job_max_attempts: int = 5
    job_lease_seconds: int = 120
    worker_concurrency: int = 4

    @model_validator(mode="after")
    def production_credentials_are_complete(self) -> "Settings":
        if self.environment.lower() != "production":
            return self
        required = {
            "DATABASE_URL": self.database_url,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_PUBLISHABLE_KEY (or SUPABASE_ANON_KEY)": self.supabase_anon_key,
            "OPENAI_API_KEY": self.openai_api_key,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError(f"Missing required production settings: {', '.join(missing)}")
        return self

    @field_validator("database_url", "supabase_anon_key", "openai_api_key", mode="before")
    @classmethod
    def empty_secret_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "openai_model_interpreter",
        "openai_model_continuity",
        "openai_model_resumption",
        "openai_embedding_model",
        mode="before",
    )
    @classmethod
    def empty_model_uses_default(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, str) or value.strip():
            return value
        defaults = {
            "openai_model_interpreter": "gpt-5.4-mini",
            "openai_model_continuity": "gpt-5.4-mini",
            "openai_model_resumption": "gpt-5.4-mini",
            "openai_embedding_model": "text-embedding-3-small",
        }
        field_name = info.field_name
        if field_name is None:
            return value
        return defaults[field_name]

    def retrieval_weights(self) -> dict[str, float]:
        return {
            "rediscovery_value": self.retrieval_weight_rediscovery,
            "capacity_fit": self.retrieval_weight_capacity,
            "context_fit": self.retrieval_weight_context,
            "open_loop_value": self.retrieval_weight_open_loop,
            "thread_momentum": self.retrieval_weight_thread_momentum,
            "personal_kind_affinity": self.retrieval_weight_kind_affinity,
            "explicit_temporal_relevance": self.retrieval_weight_temporal,
            "novelty": self.retrieval_weight_novelty,
        }

    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
