from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # === App ===
    ENVIRONMENT: str = "development"  # development | staging | production
    LOG_LEVEL: str = "INFO"

    # === Supabase ===
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # === E2B Sandbox ===
    E2B_API_KEY: str

    # === LLM ===
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GITHUB_TOKEN: str = ""

    # === Redis ===
    REDIS_URL: str = "redis://localhost:6379"

    # === Composio ===
    COMPOSIO_API_KEY: str = ""
    COMPOSIO_BASE_URL: str = "https://backend.composio.dev/api/v1"

    # === Optional: Integration credentials (fallback) ===
    DD_API_KEY: str | None = None
    DD_APP_KEY: str | None = None
    DD_SITE: str = "datadoghq.com"
    SENTRY_AUTH_TOKEN: str | None = None
    SENTRY_ORG_SLUG: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_DEFAULT_REGION: str = "us-east-1"
    GRAFANA_INSTANCE_URL: str | None = None
    GRAFANA_READ_TOKEN: str | None = None
    PAGERDUTY_API_KEY: str | None = None

    # === Frontend URL (for OAuth redirects) ===
    FRONTEND_URL: str = "http://localhost:5173"

    # === CORS ===
    # Comma-separated list of extra allowed origins, beyond FRONTEND_URL and localhost.
    EXTRA_CORS_ORIGINS: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("prod", "production")

    @property
    def cors_origins(self) -> list[str]:
        origins = {"http://localhost:5173", self.FRONTEND_URL}
        origins.update(o.strip() for o in self.EXTRA_CORS_ORIGINS.split(",") if o.strip())
        return sorted(origins)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Prefer this over the module-level singleton
    in new code so tests can override env vars before first access."""
    return Settings()


# Backward-compatible module-level singleton used throughout the codebase.
settings = get_settings()
