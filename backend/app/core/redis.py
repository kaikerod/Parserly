from collections.abc import AsyncIterator

from redis.asyncio import Redis

from app.core.config import get_settings

_redis_client: Redis | None = None


def get_redis_connection() -> Redis:
    global _redis_client

    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            health_check_interval=30,
            retry_on_timeout=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    return _redis_client


async def get_redis_client() -> AsyncIterator[Redis]:
    yield get_redis_connection()
