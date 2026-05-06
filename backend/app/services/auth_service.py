from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import time
from uuid import UUID, uuid4

import jwt
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.quotas import FREE_ANALYSIS_LIMIT, get_guest_analyses_used
from app.models.user import User
from app.services.email_service import EmailDeliveryError, EmailService

MAGIC_LINK_TTL_SECONDS = 15 * 60
MAGIC_LINK_RATE_LIMIT_SECONDS = 10 * 60
MAGIC_LINK_RATE_LIMIT_MAX_REQUESTS = 3
MAGIC_LINK_IP_RATE_LIMIT_SECONDS = 10 * 60
MAGIC_LINK_IP_RATE_LIMIT_MAX_REQUESTS = 12
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
    requires_payment: bool


@dataclass(frozen=True, slots=True)
class AuthSession:
    user_id: UUID
    access_token: str
    expires_in: int
    requires_payment: bool


@dataclass(frozen=True, slots=True)
class MagicLinkPayload:
    email: str
    requires_payment: bool = False
    existing_user: bool = False


class AuthService:
    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        settings: Settings,
        email_service: EmailService,
    ) -> None:
        self.db_session = db_session
        self.redis = redis_client
        self.settings = settings
        self.email_service = email_service

    async def request_magic_link(
        self,
        email: str,
        *,
        guest_id: str | None = None,
        client_ip: str | None = None,
    ) -> MagicLinkRequestResult:
        normalized_email = email.lower()
        await self._enforce_magic_link_rate_limit(normalized_email, client_ip)

        token = uuid4()
        magic_link = self._build_magic_link(token)
        user = await self._get_user_by_email(normalized_email)
        existing_user = user is not None
        requires_payment = (
            user.analyses_used >= FREE_ANALYSIS_LIMIT
            if user is not None
            else await self._is_guest_quota_exhausted(guest_id)
        )
        magic_link_key = self._magic_link_key(token)
        await self.redis.set(
            magic_link_key,
            self._encode_magic_link_payload(
                MagicLinkPayload(
                    email=normalized_email,
                    requires_payment=requires_payment,
                    existing_user=existing_user,
                )
            ),
            ex=MAGIC_LINK_TTL_SECONDS,
        )

        try:
            await self.email_service.send_magic_link(
                email=normalized_email,
                magic_link=magic_link,
                expires_in=MAGIC_LINK_TTL_SECONDS,
            )
        except EmailDeliveryError:
            await self.redis.delete(magic_link_key)
            raise

        return MagicLinkRequestResult(
            email=normalized_email,
            magic_link=magic_link,
            expires_in=MAGIC_LINK_TTL_SECONDS,
            requires_payment=requires_payment,
        )

    async def verify_magic_link(
        self,
        token: UUID,
        *,
        guest_id: str | None = None,
    ) -> AuthSession:
        if token.version != 4:
            raise InvalidMagicLinkToken

        payload = await self._get_magic_link_payload(token)
        if payload is None:
            raise InvalidMagicLinkToken

        consumed_payload = await self._consume_magic_link(token)
        if consumed_payload is None or consumed_payload.email != payload.email:
            raise InvalidMagicLinkToken

        user = await self._get_or_create_user(payload.email)
        requires_payment = payload.requires_payment
        if not payload.existing_user:
            requires_payment = requires_payment or await self._is_guest_quota_exhausted(
                guest_id
            )
        if requires_payment:
            await self._mark_user_free_quota_exhausted(user)

        access_token = self.create_access_token(user.id)

        return AuthSession(
            user_id=user.id,
            access_token=access_token,
            expires_in=JWT_TTL_SECONDS,
            requires_payment=requires_payment,
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

    async def _enforce_magic_link_rate_limit(
        self,
        email: str,
        client_ip: str | None,
    ) -> None:
        await self._enforce_rate_limit(
            key=self._magic_link_rate_limit_key(email),
            window_seconds=MAGIC_LINK_RATE_LIMIT_SECONDS,
            max_requests=MAGIC_LINK_RATE_LIMIT_MAX_REQUESTS,
        )

        if client_ip:
            await self._enforce_rate_limit(
                key=self._magic_link_ip_rate_limit_key(client_ip),
                window_seconds=MAGIC_LINK_IP_RATE_LIMIT_SECONDS,
                max_requests=MAGIC_LINK_IP_RATE_LIMIT_MAX_REQUESTS,
            )

    async def _enforce_rate_limit(
        self,
        *,
        key: str,
        window_seconds: int,
        max_requests: int,
    ) -> None:
        result = await self.redis.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            key,
            window_seconds,
        )
        current_count, ttl = int(result[0]), int(result[1])
        if current_count > max_requests:
            raise RateLimitExceeded(retry_after=max(ttl, 1))

    async def _consume_magic_link(self, token: UUID) -> MagicLinkPayload | None:
        value = await self.redis.eval(_GET_AND_DELETE_SCRIPT, 1, self._magic_link_key(token))
        return self._decode_magic_link_payload(value)

    async def _get_magic_link_payload(self, token: UUID) -> MagicLinkPayload | None:
        value = await self.redis.get(self._magic_link_key(token))
        return self._decode_magic_link_payload(value)

    @staticmethod
    def _decode_redis_value(value: object) -> str | None:
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

    async def _is_guest_quota_exhausted(self, guest_id: str | None) -> bool:
        analyses_used = await get_guest_analyses_used(self.redis, guest_id)
        return analyses_used >= FREE_ANALYSIS_LIMIT

    async def _mark_user_free_quota_exhausted(self, user: User) -> None:
        if user.analyses_used >= FREE_ANALYSIS_LIMIT:
            return

        await self.db_session.execute(
            update(User)
            .where(User.id == user.id, User.analyses_used < FREE_ANALYSIS_LIMIT)
            .values(
                analyses_used=FREE_ANALYSIS_LIMIT,
                updated_at=func.now(),
            )
        )

        try:
            await self.db_session.commit()
        except Exception:
            await self.db_session.rollback()
            raise

        user.analyses_used = FREE_ANALYSIS_LIMIT

    @staticmethod
    def _encode_magic_link_payload(payload: MagicLinkPayload) -> str:
        return json.dumps(
            {
                "email": payload.email,
                "requires_payment": payload.requires_payment,
                "existing_user": payload.existing_user,
            },
            separators=(",", ":"),
        )

    @classmethod
    def _decode_magic_link_payload(cls, value: object) -> MagicLinkPayload | None:
        decoded_value = cls._decode_redis_value(value)
        if decoded_value is None:
            return None

        try:
            payload = json.loads(decoded_value)
        except json.JSONDecodeError:
            return MagicLinkPayload(email=decoded_value)

        if not isinstance(payload, dict) or not isinstance(payload.get("email"), str):
            return None

        return MagicLinkPayload(
            email=payload["email"],
            requires_payment=bool(payload.get("requires_payment")),
            existing_user=bool(payload.get("existing_user")),
        )

    def _build_magic_link(self, token: UUID) -> str:
        app_url = self.settings.app_url.rstrip("/")
        return f"{app_url}/auth/verify?token={token}"

    @staticmethod
    def _magic_link_key(token: UUID) -> str:
        return f"auth:magic-link:{token}"

    @staticmethod
    def _magic_link_rate_limit_key(email: str) -> str:
        email_hash = sha256(email.encode("utf-8")).hexdigest()
        return f"auth:magic-link:rate:{email_hash}"

    @staticmethod
    def _magic_link_ip_rate_limit_key(client_ip: str) -> str:
        ip_hash = sha256(client_ip.encode("utf-8")).hexdigest()
        return f"auth:magic-link:ip-rate:{ip_hash}"

    @staticmethod
    def _jwt_blocklist_key(access_token: str) -> str:
        token_hash = sha256(access_token.encode("utf-8")).hexdigest()
        return f"auth:jwt:blocklist:{token_hash}"
