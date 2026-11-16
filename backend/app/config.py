"""Application configuration loaded from environment variables (never from Git)."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://synagogue:devpass-local-only@127.0.0.1:5432/synagogue"
    # Cookie security: must be true in production (HTTPS). Dev over http://localhost uses false.
    cookie_secure: bool = False
    session_hours: int = 12
    # Comma separated list of allowed CORS origins (exact). Empty = same-origin only.
    cors_origins: str = ""
    media_dir: Path = Path("./data/media")
    max_upload_mb: int = 5
    # Optional: serve built frontends from the API process (single-origin deployment)
    admin_static_dir: Path | None = None
    display_static_dir: Path | None = None
    # Bootstrap admin (only used when there are no users)
    admin_username: str | None = None
    admin_password: str | None = None
    snapshot_days: int = 400  # > 12 months of pre-computed calendar data
    login_max_failures: int = 5
    login_window_minutes: int = 15
    environment: str = "development"

    @field_validator("database_url")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        # Render / Heroku give postgres:// or postgresql:// — use the psycopg 3 driver
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
