from __future__ import annotations

from uuid import UUID

from redis.asyncio import Redis

FREE_ANALYSIS_LIMIT = 3
GUEST_ANALYSIS_COOKIE_NAME = "parserly_guest_id"
GUEST_ANALYSIS_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180
GUEST_ANALYSIS_KEY_TTL_SECONDS = GUEST_ANALYSIS_COOKIE_MAX_AGE_SECONDS


def normalize_guest_id(raw_guest_id: str | None) -> str | None:
    if not raw_guest_id:
        return None

    try:
        return str(UUID(raw_guest_id))
    except ValueError:
        return None


async def get_guest_analyses_used(redis_client: Redis, guest_id: str | None) -> int:
    if guest_id is None:
        return 0

    raw_value = await redis_client.get(guest_analysis_key(guest_id))
    if raw_value is None:
        return 0

    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8")

    try:
        return max(0, int(raw_value))
    except (TypeError, ValueError):
        return 0


def guest_analysis_key(guest_id: str) -> str:
    return f"analysis:guest:{guest_id}:used"
