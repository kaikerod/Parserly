from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
DEFAULT_OPENROUTER_MODEL = "google/gemma-4-26b-a4b-it:free"
DEFAULT_OPENROUTER_FALLBACK_MODEL = "google/gemma-4-26b-a4b-it"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_url: str = "http://localhost:8000"
    secret_key: str = "change-me-only-for-local-development"
    environment: str = "development"
    vercel: bool = False

    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/ats_db"
    redis_url: str = "redis://localhost:6379/0"

    openrouter_api_key: str = ""
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
    openrouter_fallback_model: str = DEFAULT_OPENROUTER_FALLBACK_MODEL

    abacatepay_api_key: str = ""
    abacatepay_api_url: str = "https://api.abacatepay.com/v2"
    abacatepay_webhook_secret: str = ""
    analysis_price_cents: int = 1990

    resend_api_key: str = ""
    email_from: str = "noreply@localhost"
    upload_tmp_dir: str = "/tmp/parserly_uploads"

    auth_cookie_name: str = "access_token"
    auth_cookie_secure: bool = True
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "strict"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_asyncpg_database_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized_url = value
        if value.startswith("postgres://"):
            normalized_url = f"postgresql+asyncpg://{value.removeprefix('postgres://')}"
        elif value.startswith("postgresql://"):
            normalized_url = f"postgresql+asyncpg://{value.removeprefix('postgresql://')}"

        return normalize_asyncpg_ssl_query(normalized_url)


def normalize_asyncpg_ssl_query(database_url: str) -> str:
    parsed_url = urlsplit(database_url)
    query_items = parse_qsl(parsed_url.query, keep_blank_values=True)
    normalized_query_items: list[tuple[str, str]] = []
    ssl_mode: str | None = None

    for key, query_value in query_items:
        if key == "sslmode":
            ssl_mode = query_value
            continue
        normalized_query_items.append((key, query_value))

    has_asyncpg_ssl = any(key == "ssl" for key, _ in normalized_query_items)
    if ssl_mode is not None and not has_asyncpg_ssl:
        normalized_query_items.append(("ssl", ssl_mode))

    if ssl_mode is None:
        return database_url

    return urlunsplit(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            urlencode(normalized_query_items),
            parsed_url.fragment,
        )
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
