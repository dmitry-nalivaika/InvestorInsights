"""
Application configuration using Pydantic BaseSettings.

Validates all environment variables at startup.
See reference/env-config.md for the complete variable reference.
"""

from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    app_name: str = "investorinsights"
    app_version: str = "1.0.0"
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    log_level: str = "INFO"
    api_key: str = Field(..., description="API authentication key for V1 auth")

    # ── Database ─────────────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "company_analysis"
    db_user: str = "analyst"
    db_password: str = "analyst_password"
    database_url: Optional[str] = None
    # Pool sizing — per-worker connection budget.
    # Total connections = api_workers × (db_pool_size + db_max_overflow).
    #   Dev  (1 worker):  5 + 5  = 10  (local PostgreSQL, plenty of headroom)
    #   Prod (4 workers):  5 + 10 = 15 × 4 = 60 (Azure Flex GP_Gen5_2: 100 limit)
    # Azure B2s (50 conn) → keep pool_size ≤ 5, overflow ≤ 5 per worker.
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_ssl_mode: str = "prefer"

    # ── Vector Store (Qdrant) ────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_http_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    qdrant_collection_prefix: str = "company_"

    # ── Object Storage (Azure Blob) ──────────────────────────────
    azure_storage_connection_string: str = ""
    azure_storage_account_name: str = ""
    azure_storage_container_filings: str = "filings"
    azure_storage_container_exports: str = "exports"

    # ── Redis ────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_password: Optional[str] = None
    redis_ssl: bool = False
    redis_max_connections: int = Field(default=20, ge=1)

    # ── Celery ───────────────────────────────────────────────────
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    worker_concurrency: int = Field(default=4, ge=1, le=32)
    celery_task_time_limit: int = Field(default=600, ge=60)
    celery_task_soft_time_limit: int = Field(default=540, ge=30)

    # ── Azure OpenAI ─────────────────────────────────────────────
    llm_provider: LLMProvider = LLMProvider.AZURE_OPENAI
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-large"

    # ── OpenAI Direct (fallback) ─────────────────────────────────
    openai_api_key: Optional[str] = None

    # ── LLM Configuration ────────────────────────────────────────
    llm_model: str = "gpt-4o-mini"
    llm_fallback_model: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=4096, ge=256, le=16384)
    llm_timeout: int = Field(default=120, ge=10)
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = Field(default=3072, ge=256)
    embedding_batch_size: int = Field(default=64, ge=1, le=2048)

    # ── RAG Configuration ────────────────────────────────────────
    rag_top_k: int = Field(default=15, ge=1, le=50)
    rag_score_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    rag_max_context_tokens: int = Field(default=12000, ge=1000)
    rag_max_history_tokens: int = Field(default=4000, ge=500)
    rag_max_history_exchanges: int = Field(default=10, ge=1, le=50)

    # ── Ingestion Configuration ──────────────────────────────────
    chunk_size: int = Field(default=768, ge=512, le=1024)
    chunk_overlap: int = Field(default=128, ge=0, le=512)
    max_upload_size_mb: int = Field(default=50, ge=1, le=500)

    # ── SEC EDGAR ────────────────────────────────────────────────
    sec_edgar_user_agent: str = "InvestorInsights/1.0 (your-email@example.com)"
    sec_edgar_rate_limit: int = Field(default=10, ge=1, le=10)
    sec_edgar_base_url: str = "https://data.sec.gov"

    # ── API Server ───────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1024, le=65535)
    api_workers: int = Field(default=4, ge=1, le=32)
    api_rate_limit_crud: int = Field(default=100, ge=1)
    api_rate_limit_chat: int = Field(default=20, ge=1)

    # ── Observability ────────────────────────────────────────────
    applicationinsights_connection_string: Optional[str] = None
    otel_service_name: str = "investorinsights-api"

    # ── Computed Properties ──────────────────────────────────────

    @model_validator(mode="after")
    def _build_computed_urls(self) -> "Settings":
        """Build computed URLs from component parts if not explicitly set."""
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        if not self.qdrant_url:
            self.qdrant_url = f"http://{self.qdrant_host}:{self.qdrant_http_port}"
        if not self.celery_broker_url:
            self.celery_broker_url = self.redis_url
        if not self.celery_result_backend:
            self.celery_result_backend = self.redis_url
        return self

    @field_validator("sec_edgar_user_agent")
    @classmethod
    def _validate_sec_user_agent(cls, v: str) -> str:
        """SEC EDGAR requires User-Agent with email address."""
        if "@" not in v or "(" not in v:
            raise ValueError(
                "SEC EDGAR User-Agent must contain an email address in format: "
                "'AppName/Version (email@example.com)'"
            )
        return v

    @model_validator(mode="after")
    def _validate_llm_provider_config(self) -> "Settings":
        """Validate that the chosen LLM provider has required config."""
        if self.llm_provider == LLMProvider.AZURE_OPENAI:
            if not self.azure_openai_api_key:
                raise ValueError(
                    "AZURE_OPENAI_API_KEY is required when LLM_PROVIDER=azure_openai"
                )
            if not self.azure_openai_endpoint:
                raise ValueError(
                    "AZURE_OPENAI_ENDPOINT is required when LLM_PROVIDER=azure_openai"
                )
        elif self.llm_provider == LLMProvider.OPENAI:
            if not self.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnvironment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.app_env == AppEnvironment.DEVELOPMENT

    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        if self.database_url:
            return self.database_url.replace("+asyncpg", "")
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Call this to get the application config."""
    return Settings()  # type: ignore[call-arg]
