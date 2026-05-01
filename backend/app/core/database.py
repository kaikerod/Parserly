from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker

    if _sessionmaker is None:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )

    return _sessionmaker


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        yield session
