"""Application settings loaded from environment variables (.env)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration. Every value can be overridden by an environment variable."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Ymmo"
    app_env: str = "development"
    app_debug: bool = False

    secret_key: str = Field(default="dev-only-insecure-key-change-me", min_length=16)
    access_token_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"

    postgres_user: str = "ymmo"
    postgres_password: str = "ymmo"
    postgres_db: str = "ymmo"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    # When set, overrides the PostgreSQL settings above (used by tests: sqlite://)
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")

    seed_on_startup: bool = False
    media_dir: str = "media"
    analytics_model_path: str = "analytics/models/price_model.joblib"

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Single cached instance (avoids re-reading .env on every request)."""
    return Settings()
