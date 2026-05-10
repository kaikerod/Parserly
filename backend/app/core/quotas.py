from __future__ import annotations

import hmac
from hashlib import sha256
from uuid import UUID

from redis.asyncio import Redis

FREE_ANALYSIS_LIMIT = 2
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

    return await get_guest_analyses_used_by_key(redis_client, guest_analysis_key(guest_id))


def normalize_analysis_count(raw_value: object) -> int:
    try:
        return max(0, int(raw_value or 0))
    except (TypeError, ValueError):
        return 0


def get_free_analyses_remaining(raw_analyses_used: object) -> int:
    return max(0, FREE_ANALYSIS_LIMIT - normalize_analysis_count(raw_analyses_used))


def get_paid_analysis_credits(user: object) -> int:
    return normalize_analysis_count(getattr(user, "paid_analysis_credits", 0))


def get_user_remaining_analyses(user: object) -> int:
    analyses_used = getattr(user, "analyses_used", 0)
    return get_free_analyses_remaining(analyses_used) + get_paid_analysis_credits(user)


def user_requires_payment(user: object) -> bool:
    return get_user_remaining_analyses(user) == 0


def guest_analysis_key(guest_id: str) -> str:
    return f"analysis:guest:{guest_id}:used"


def guest_analysis_client_key(secret_key: str, client_ip: str | None) -> str | None:
    if not client_ip or client_ip == "unknown":
        return None

    normalized_ip = client_ip.strip().lower()
    if not normalized_ip:
        return None

    digest = hmac.new(
        secret_key.encode("utf-8"),
        f"parserly:guest-analysis:v1:{normalized_ip}".encode("utf-8"),
        sha256,
    ).hexdigest()
    return f"analysis:guest-client:{digest}:used"


async def get_guest_analyses_used_by_key(redis_client: Redis, key: str | None) -> int:
    if key is None:
        return 0

    raw_value = await redis_client.get(key)
    if raw_value is None:
        return 0

    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8")

    return normalize_analysis_count(raw_value)
