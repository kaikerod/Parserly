from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
DEFAULT_OPENROUTER_MODEL = "google/gemma-4-26b-a4b-it:free"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_url: str = "http://localhost:8000"
    secret_key: str = "change-me-only-for-local-development"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/ats_db"
    redis_url: str = "redis://localhost:6379/0"

    openrouter_api_key: str = ""
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
    openrouter_fallback_model: str = DEFAULT_OPENROUTER_MODEL

    abacatepay_api_key: str = ""
    abacatepay_api_url: str = "https://api.abacatepay.com/v2"
    abacatepay_webhook_secret: str = ""
    analysis_price_cents: int = 1990

    resend_api_key: str = ""
    email_from: str = "noreply@localhost"
    upload_tmp_dir: str = ""

    auth_cookie_name: str = "access_token"
    auth_cookie_secure: bool = True
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "strict"


@lru_cache
def get_settings() -> Settings:
    return Settings()
