from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine

    if _engine is None:
        settings = get_settings()
        database_url, connect_args = prepare_asyncpg_connection(settings.database_url)
        _engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=2,
            pool_recycle=300,
            connect_args=connect_args,
        )

    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker

    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
        )

    return _sessionmaker


async def init_development_database() -> None:
    settings = get_settings()
    if should_skip_automatic_schema_creation(settings):
        return

    from app.models import Base

    async with get_engine().begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await connection.run_sync(Base.metadata.create_all)


def should_skip_automatic_schema_creation(settings: Settings) -> bool:
    return settings.environment.lower() == "production" or settings.vercel


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        yield session


def prepare_asyncpg_connection(database_url: str) -> tuple[str, dict[str, object]]:
    parsed_url = urlsplit(database_url)
    if parsed_url.scheme != "postgresql+asyncpg":
        return database_url, {}

    query_items = parse_qsl(parsed_url.query, keep_blank_values=True)
    normalized_query_items: list[tuple[str, str]] = []
    ssl_enabled = False

    asyncpg_unsupported_query_keys = {
        "channel_binding",
        "sslcert",
        "sslkey",
        "sslrootcert",
    }

    for key, value in query_items:
        if key in {"ssl", "sslmode"}:
            if value.lower() not in {"", "0", "false", "disable", "disabled"}:
                ssl_enabled = True
            continue
        if key in asyncpg_unsupported_query_keys:
            continue
        normalized_query_items.append((key, value))

    normalized_url = urlunsplit(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            urlencode(normalized_query_items),
            parsed_url.fragment,
        )
    )
    connect_args: dict[str, object] = {"ssl": True} if ssl_enabled else {}
    return normalized_url, connect_args
