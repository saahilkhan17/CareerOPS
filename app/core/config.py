"""Application configuration via environment variables (pydantic-settings)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Override with environment variables or a `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "careerops"
    env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://careerops:careerops@localhost:5432/careerops"
    redis_url: str = "redis://localhost:6379/0"
    auth_secret_key: str | None = None
    match_weight_required: float = 0.5
    match_weight_preferred: float = 0.2
    match_weight_experience: float = 0.2
    match_weight_title: float = 0.1
    match_llm_enabled: bool = False
    ingest_greenhouse_boards: dict[str, str] = {}
    ingest_lever_companies: dict[str, str] = {}
    ingest_remoteok_enabled: bool = True
    ingest_http_retries: int = 3
    ingest_http_backoff: float = 1.0
    ingest_min_interval: float = 1.0
    ingest_automatch_limit: int = 500
    celery_eager: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
