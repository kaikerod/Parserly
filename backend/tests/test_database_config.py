from app.core.config import Settings
from app.core.database import prepare_asyncpg_connection


def test_settings_uses_canonical_api_url_for_vercel_production_default() -> None:
    settings = Settings(
        vercel=True,
        vercel_env="production",
        api_public_url="http://localhost:8000",
    )

    assert settings.api_public_url == "https://parserly-api.vercel.app"


def test_settings_replaces_immutable_vercel_api_url_in_production() -> None:
    settings = Settings(
        vercel=True,
        vercel_env="production",
        api_public_url="https://parserly-g2b4ih1a1-kaikerods-projects.vercel.app/",
    )

    assert settings.api_public_url == "https://parserly-api.vercel.app"


def test_settings_keeps_custom_api_public_url_for_vercel_production() -> None:
    settings = Settings(
        vercel=True,
        vercel_env="production",
        api_public_url="https://api.parserly.com.br",
    )

    assert settings.api_public_url == "https://api.parserly.com.br"


def test_settings_normalizes_postgres_scheme_without_rewriting_sslmode() -> None:
    settings = Settings(
        database_url="postgres://user:pass@example.com/db?sslmode=require",
    )

    assert settings.database_url == (
        "postgresql+asyncpg://user:pass@example.com/db?sslmode=require"
    )


def test_prepare_asyncpg_connection_converts_ssl_query_to_connect_args() -> None:
    database_url, connect_args = prepare_asyncpg_connection(
        "postgresql+asyncpg://user:pass@example.com/db?sslmode=require&channel_binding=require"
    )

    assert database_url == "postgresql+asyncpg://user:pass@example.com/db"
    assert connect_args == {"ssl": True}


def test_prepare_asyncpg_connection_leaves_local_non_ssl_url_unchanged() -> None:
    database_url, connect_args = prepare_asyncpg_connection(
        "postgresql+asyncpg://user:pass@localhost/db"
    )

    assert database_url == "postgresql+asyncpg://user:pass@localhost/db"
    assert connect_args == {}
