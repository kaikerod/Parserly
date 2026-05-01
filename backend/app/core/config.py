from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_url: str = "http://localhost:8000"
    secret_key: str = "change-me-only-for-local-development"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/ats_db"
    redis_url: str = "redis://localhost:6379/0"

    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-flash-1.5"
    openrouter_fallback_model: str = "openai/gpt-4o-mini"

    abacatepay_api_key: str = ""
    abacatepay_api_url: str = "https://api.abacatepay.com/v2"
    abacatepay_webhook_secret: str = ""
    analysis_price_cents: int = 1990

    auth_cookie_name: str = "access_token"
    auth_cookie_secure: bool = True
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "strict"


@lru_cache
def get_settings() -> Settings:
    return Settings()
