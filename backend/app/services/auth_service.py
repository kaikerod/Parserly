from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import time
from uuid import UUID, uuid4

import jwt
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.user import User

MAGIC_LINK_TTL_SECONDS = 15 * 60
MAGIC_LINK_RATE_LIMIT_SECONDS = 10 * 60
MAGIC_LINK_RATE_LIMIT_MAX_REQUESTS = 3
JWT_TTL_SECONDS = 7 * 24 * 60 * 60
JWT_ALGORITHM = "HS256"

_RATE_LIMIT_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
local ttl = redis.call("TTL", KEYS[1])
return { current, ttl }
"""

_GET_AND_DELETE_SCRIPT = """
local value = redis.call("GET", KEYS[1])
if value then
    redis.call("DEL", KEYS[1])
end
return value
"""


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("magic link rate limit exceeded")


class InvalidMagicLinkToken(Exception):
    pass


@dataclass(frozen=True, slots=True)
class MagicLinkRequestResult:
    email: str
    magic_link: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class AuthSession:
    user_id: UUID
    access_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        settings: Settings,
    ) -> None:
        self.db_session = db_session
        self.redis = redis_client
        self.settings = settings

    async def request_magic_link(self, email: str) -> MagicLinkRequestResult:
        normalized_email = email.lower()
        await self._enforce_magic_link_rate_limit(normalized_email)

        token = uuid4()
        magic_link = self._build_magic_link(token)
        await self.redis.set(
            self._magic_link_key(token),
            normalized_email,
            ex=MAGIC_LINK_TTL_SECONDS,
        )

        return MagicLinkRequestResult(
            email=normalized_email,
            magic_link=magic_link,
            expires_in=MAGIC_LINK_TTL_SECONDS,
        )

    async def verify_magic_link(self, token: UUID) -> AuthSession:
        if token.version != 4:
            raise InvalidMagicLinkToken

        email = await self._consume_magic_link(token)
        if email is None:
            raise InvalidMagicLinkToken

        user = await self._get_or_create_user(email)
        access_token = self.create_access_token(user.id)

        return AuthSession(
            user_id=user.id,
            access_token=access_token,
            expires_in=JWT_TTL_SECONDS,
        )

    async def logout(self, access_token: str | None) -> None:
        if not access_token:
            return

        try:
            payload = jwt.decode(
                access_token,
                self.settings.secret_key,
                algorithms=[JWT_ALGORITHM],
            )
        except jwt.InvalidTokenError:
            return

        exp = payload.get("exp")
        if not isinstance(exp, int):
            return

        ttl = exp - int(time())
        if ttl <= 0:
            return

        await self.redis.set(
            self._jwt_blocklist_key(access_token),
            "1",
            ex=ttl,
        )

    async def is_access_token_blocklisted(self, access_token: str) -> bool:
        return bool(await self.redis.exists(self._jwt_blocklist_key(access_token)))

    def create_access_token(self, user_id: UUID) -> str:
        expires_at = datetime.now(UTC) + timedelta(seconds=JWT_TTL_SECONDS)
        payload = {
            "user_id": str(user_id),
            "exp": expires_at,
        }
        return jwt.encode(payload, self.settings.secret_key, algorithm=JWT_ALGORITHM)

    async def _enforce_magic_link_rate_limit(self, email: str) -> None:
        key = self._magic_link_rate_limit_key(email)
        result = await self.redis.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            key,
            MAGIC_LINK_RATE_LIMIT_SECONDS,
        )
        current_count, ttl = int(result[0]), int(result[1])
        if current_count > MAGIC_LINK_RATE_LIMIT_MAX_REQUESTS:
            raise RateLimitExceeded(retry_after=max(ttl, 1))

    async def _consume_magic_link(self, token: UUID) -> str | None:
        value = await self.redis.eval(_GET_AND_DELETE_SCRIPT, 1, self._magic_link_key(token))
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    async def _get_or_create_user(self, email: str) -> User:
        user = await self._get_user_by_email(email)
        if user is not None:
            return user

        user = User(email=email)
        self.db_session.add(user)

        try:
            await self.db_session.commit()
        except IntegrityError:
            await self.db_session.rollback()
            user = await self._get_user_by_email(email)
            if user is None:
                raise
            return user

        await self.db_session.refresh(user)
        return user

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.db_session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    def _build_magic_link(self, token: UUID) -> str:
        app_url = self.settings.app_url.rstrip("/")
        return f"{app_url}/api/v1/auth/verify?token={token}"

    @staticmethod
    def _magic_link_key(token: UUID) -> str:
        return f"auth:magic-link:{token}"

    @staticmethod
    def _magic_link_rate_limit_key(email: str) -> str:
        email_hash = sha256(email.encode("utf-8")).hexdigest()
        return f"auth:magic-link:rate:{email_hash}"

    @staticmethod
    def _jwt_blocklist_key(access_token: str) -> str:
        token_hash = sha256(access_token.encode("utf-8")).hexdigest()
        return f"auth:jwt:blocklist:{token_hash}"
