from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
DEFAULT_OPENROUTER_MODEL = "google/gemma-4-26b-a4b-it:free"
DEFAULT_OPENROUTER_FALLBACK_MODEL = "google/gemma-4-26b-a4b-it"
CANONICAL_API_PUBLIC_URL = "https://parserly-api.vercel.app"
LOCAL_API_PUBLIC_URLS = {"", "http://localhost:8000"}


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
    vercel_env: str = ""
    vercel_target_env: str = ""

    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/ats_db"
    redis_url: str = "redis://localhost:6379/0"
    api_public_url: str = "http://localhost:8000"

    openrouter_api_key: str = ""
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
    openrouter_fallback_model: str = DEFAULT_OPENROUTER_FALLBACK_MODEL

    mercadopago_access_token: str = ""
    mercadopago_api_url: str = "https://api.mercadopago.com"
    mercadopago_webhook_secret: str = ""
    mercadopago_mock_payments: bool = False
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

        return normalized_url

    @model_validator(mode="after")
    def use_canonical_api_url_for_vercel_production(self) -> "Settings":
        if not self._is_vercel_production():
            return self

        normalized_api_url = self.api_public_url.strip().rstrip("/")
        if (
            normalized_api_url in LOCAL_API_PUBLIC_URLS
            or _is_parserly_immutable_deployment_url(normalized_api_url)
        ):
            self.api_public_url = CANONICAL_API_PUBLIC_URL

        return self

    def _is_vercel_production(self) -> bool:
        return self.vercel and (
            self.vercel_env == "production" or self.vercel_target_env == "production"
        )


def _is_parserly_immutable_deployment_url(url: str) -> bool:
    if not url.startswith("https://parserly-"):
        return False

    if not url.endswith("-kaikerods-projects.vercel.app"):
        return False

    deployment_id = url.removeprefix("https://parserly-").removesuffix(
        "-kaikerods-projects.vercel.app"
    )
    return deployment_id.isalnum()


@lru_cache
def get_settings() -> Settings:
    return Settings()
