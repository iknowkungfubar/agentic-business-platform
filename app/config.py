"""Application settings — type-safe configuration via pydantic-settings.

Loads from environment variables with sensible defaults.
For production, override via environment or .env file.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Platform configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────
    database_url: str = "sqlite:///./turin.db"

    # ── Auth ──────────────────────────────────────────────────────
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # ── API ───────────────────────────────────────────────────────
    cors_origins: str = "*"
    rate_limit_max: int = 10
    rate_limit_window: int = 60

    # ── Inference ─────────────────────────────────────────────────
    inference_url: str = "http://localhost:1234/v1"
    inference_model: str = "qwen3.5-9b-deepseek-v4-flash"
    inference_timeout: int = 30

    # ── Observability ─────────────────────────────────────────────
    log_level: str = "info"
    disable_rate_limit: bool = False

    # ── OIDC / SSO ───────────────────────────────────────────────
    oidc_jwks_url: str = ""
    oidc_issuer: str = ""

    # ── Storage ──────────────────────────────────────────────────
    upload_dir: str = "/tmp/turin-uploads"

    # ── Deployment ────────────────────────────────────────────────
    environment: str = "development"
    debug: bool = False


# Singleton — import this, don't instantiate Settings directly
settings = Settings()
