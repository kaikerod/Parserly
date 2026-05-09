from __future__ import annotations

from hashlib import sha256

from fastapi import Request
from redis.asyncio import Redis

_RATE_LIMIT_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
local ttl = redis.call("TTL", KEYS[1])
return { current, ttl }
"""


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("rate limit exceeded")


class ConcurrentRequestLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("concurrent request limit exceeded")


async def enforce_rate_limit(
    redis_client: Redis,
    *,
    scope: str,
    identifier: str,
    max_requests: int,
    window_seconds: int,
) -> None:
    result = await redis_client.eval(
        _RATE_LIMIT_SCRIPT,
        1,
        rate_limit_key(scope, identifier),
        window_seconds,
    )
    current_count, ttl = int(result[0]), int(result[1])
    if current_count > max_requests:
        raise RateLimitExceeded(retry_after=max(ttl, 1))


async def acquire_concurrency_slot(
    redis_client: Redis,
    *,
    scope: str,
    identifier: str,
    ttl_seconds: int,
) -> str:
    key = rate_limit_key(f"{scope}:inflight", identifier)
    acquired = await redis_client.set(key, "1", ex=ttl_seconds, nx=True)
    if not acquired:
        raise ConcurrentRequestLimitExceeded(retry_after=ttl_seconds)
    return key


async def release_concurrency_slot(redis_client: Redis, key: str | None) -> None:
    if key is None:
        return
    try:
        await redis_client.delete(key)
    except Exception:
        return


def rate_limit_key(scope: str, identifier: str) -> str:
    digest = sha256(identifier.encode("utf-8")).hexdigest()
    return f"rate:{scope}:{digest}"


def client_ip_from_request(request: Request) -> str:
    for header_name in ("x-vercel-forwarded-for", "x-real-ip", "x-forwarded-for"):
        raw_value = request.headers.get(header_name)
        if not raw_value:
            continue
        first_value = raw_value.split(",", 1)[0].strip()
        if first_value:
            return first_value

    if request.client is not None and request.client.host:
        return request.client.host

    return "unknown"


def retry_after_headers(exc: RateLimitExceeded) -> dict[str, str]:
    return {"Retry-After": str(exc.retry_after)}
