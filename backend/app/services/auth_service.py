from __future__ import annotations

import json
from secrets import token_urlsafe
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import time
from urllib.parse import urlencode
from uuid import UUID, uuid4

import httpx
import jwt
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import SessionAccessProfile, get_session_access_profile
from app.core.config import Settings
from app.core.quotas import (
    FREE_ANALYSIS_LIMIT,
    get_guest_analyses_used_by_key,
    get_guest_analyses_used,
    guest_analysis_client_key,
    user_requires_payment,
)
from app.models.user import User
from app.models.user_identity import UserIdentity
from app.schemas.auth import normalize_email_address
from app.services.email_service import EmailDeliveryError, EmailService

MAGIC_LINK_TTL_SECONDS = 15 * 60
MAGIC_LINK_RATE_LIMIT_SECONDS = 10 * 60
MAGIC_LINK_RATE_LIMIT_MAX_REQUESTS = 3
MAGIC_LINK_IP_RATE_LIMIT_SECONDS = 10 * 60
MAGIC_LINK_IP_RATE_LIMIT_MAX_REQUESTS = 12
JWT_TTL_SECONDS = 7 * 24 * 60 * 60
JWT_ALGORITHM = "HS256"
GOOGLE_OAUTH_PROVIDER = "google"
GOOGLE_OAUTH_SCOPE = "openid email profile"
GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_OAUTH_HTTP_TIMEOUT_SECONDS = 10.0
GOOGLE_JWKS_CACHE_TTL_SECONDS = 5 * 60
_google_jwks_cache: tuple[int, dict[str, object]] | None = None

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


class GoogleOAuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


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
    access_profile: SessionAccessProfile


@dataclass(frozen=True, slots=True)
class MagicLinkPayload:
    email: str
    requires_payment: bool = False
    existing_user: bool = False


@dataclass(frozen=True, slots=True)
class GoogleOAuthStatePayload:
    state: str
    created_at: int


@dataclass(frozen=True, slots=True)
class GoogleOAuthStartResult:
    authorization_url: str
    state: str
    cookie_name: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class GoogleOAuthTokenResult:
    id_token: str
    access_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None


@dataclass(frozen=True, slots=True)
class VerifiedGoogleIdentityClaims:
    provider_subject: str
    email: str
    email_verified: bool


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
            user_requires_payment(user)
            if user is not None
            else await self._is_guest_quota_exhausted(
                guest_id,
                client_ip=client_ip,
            )
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
        client_ip: str | None = None,
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
                guest_id,
                client_ip=client_ip,
            )
        if requires_payment:
            await self._mark_user_free_quota_exhausted(user)

        access_token = self.create_access_token(user.id)

        return AuthSession(
            user_id=user.id,
            access_token=access_token,
            expires_in=JWT_TTL_SECONDS,
            requires_payment=requires_payment,
            access_profile=get_session_access_profile(user.email),
        )

    async def create_google_authorization_url(self) -> GoogleOAuthStartResult:
        if not self.settings.google_oauth_configured:
            raise GoogleOAuthError(
                code="google-oauth-unavailable",
                message="Google OAuth is not configured.",
                status_code=503,
            )

        state = token_urlsafe(48)
        payload = GoogleOAuthStatePayload(
            state=state,
            created_at=int(time()),
        )
        expires_in = self.settings.google_oauth_state_ttl_seconds
        await self.redis.set(
            self._google_oauth_state_key(state),
            self._encode_google_oauth_state_payload(payload),
            ex=expires_in,
        )

        query = urlencode(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": self.settings.google_oauth_redirect_uri,
                "response_type": "code",
                "scope": GOOGLE_OAUTH_SCOPE,
                "state": state,
                "access_type": "offline",
                "prompt": "select_account",
            }
        )
        return GoogleOAuthStartResult(
            authorization_url=f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{query}",
            state=state,
            cookie_name=self.settings.google_oauth_state_cookie_name,
            expires_in=expires_in,
        )

    async def verify_google_oauth_callback(
        self,
        *,
        code: str | None,
        state: str | None,
        state_cookie: str | None,
        oauth_error: str | None = None,
    ) -> AuthSession:
        if oauth_error:
            raise GoogleOAuthError(
                code="google-oauth-denied",
                message="Google access was not completed.",
                status_code=400,
            )

        if not code:
            raise GoogleOAuthError(
                code="google-oauth-invalid-state",
                message="Google OAuth callback is missing an authorization code.",
                status_code=400,
            )

        await self._validate_and_consume_google_oauth_state(
            state=state,
            state_cookie=state_cookie,
        )
        token_result = await self.exchange_google_authorization_code(code)
        claims = await self.verify_google_id_token(token_result.id_token)
        user = await self._resolve_google_identity(claims)

        return AuthSession(
            user_id=user.id,
            access_token=self.create_access_token(user.id),
            expires_in=JWT_TTL_SECONDS,
            requires_payment=user_requires_payment(user),
            access_profile=get_session_access_profile(user.email),
        )

    async def exchange_google_authorization_code(self, code: str) -> GoogleOAuthTokenResult:
        if not self.settings.google_oauth_configured:
            raise GoogleOAuthError(
                code="google-oauth-unavailable",
                message="Google OAuth is not configured.",
                status_code=503,
            )

        try:
            async with httpx.AsyncClient(timeout=GOOGLE_OAUTH_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    GOOGLE_TOKEN_ENDPOINT,
                    data={
                        "code": code,
                        "client_id": self.settings.google_client_id,
                        "client_secret": self.settings.google_client_secret,
                        "redirect_uri": self.settings.google_oauth_redirect_uri,
                        "grant_type": "authorization_code",
                    },
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GoogleOAuthError(
                code="google-oauth-unavailable",
                message="Google OAuth could not be completed right now.",
                status_code=503,
            ) from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("id_token"), str):
            raise GoogleOAuthError(
                code="google-oauth-unavailable",
                message="Google OAuth returned an invalid token response.",
                status_code=503,
            )

        expires_in = payload.get("expires_in")
        return GoogleOAuthTokenResult(
            id_token=payload["id_token"],
            access_token=payload.get("access_token") if isinstance(payload.get("access_token"), str) else None,
            token_type=payload.get("token_type") if isinstance(payload.get("token_type"), str) else None,
            expires_in=expires_in if isinstance(expires_in, int) else None,
        )

    async def verify_google_id_token(self, id_token: str) -> VerifiedGoogleIdentityClaims:
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.InvalidTokenError as exc:
            raise self._invalid_google_identity_error() from exc

        key_id = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(key_id, str):
            raise self._invalid_google_identity_error()

        key_data = await self._find_google_jwks_key(key_id)
        if key_data is None:
            raise self._invalid_google_identity_error()

        try:
            signing_key = jwt.PyJWK.from_dict(key_data).key
            payload = jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256"],
                audience=self.settings.google_client_id,
                issuer=["https://accounts.google.com", "accounts.google.com"],
                options={"require": ["exp", "sub", "email"]},
            )
        except jwt.InvalidTokenError as exc:
            raise self._invalid_google_identity_error() from exc

        provider_subject = payload.get("sub")
        raw_email = payload.get("email")
        if not isinstance(provider_subject, str) or not provider_subject.strip():
            raise self._invalid_google_identity_error()
        if not isinstance(raw_email, str):
            raise self._invalid_google_identity_error()

        email_verified = payload.get("email_verified") is True or payload.get("email_verified") == "true"
        if not email_verified:
            raise GoogleOAuthError(
                code="google-email-unverified",
                message="Google did not verify this email address.",
                status_code=400,
            )

        try:
            email = normalize_email_address(raw_email)
        except ValueError as exc:
            raise self._invalid_google_identity_error() from exc

        return VerifiedGoogleIdentityClaims(
            provider_subject=provider_subject,
            email=email,
            email_verified=True,
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

    async def _get_user_by_id(self, user_id: UUID) -> User | None:
        result = await self.db_session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.db_session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def _resolve_google_identity(self, claims: VerifiedGoogleIdentityClaims) -> User:
        if not claims.email_verified:
            raise GoogleOAuthError(
                code="google-email-unverified",
                message="Google did not verify this email address.",
                status_code=400,
            )

        identity = await self._get_google_identity_by_subject(claims.provider_subject)
        if identity is not None:
            return await self._user_for_google_identity(identity, claims)

        user = await self._get_user_by_email(claims.email)
        if user is not None:
            # Automatic linking is allowed only because magic link and Google verified email both prove control of the same mailbox.
            return await self._create_google_identity_for_user(user, claims)

        user = User(email=claims.email)
        self.db_session.add(user)

        try:
            await self.db_session.flush()
            self.db_session.add(
                self._build_google_identity(
                    user=user,
                    claims=claims,
                )
            )
            await self.db_session.commit()
        except IntegrityError:
            await self.db_session.rollback()
            return await self._recover_google_identity_after_integrity_error(claims)
        except Exception:
            await self.db_session.rollback()
            raise

        await self.db_session.refresh(user)
        return user

    async def _create_google_identity_for_user(
        self,
        user: User,
        claims: VerifiedGoogleIdentityClaims,
    ) -> User:
        self.db_session.add(self._build_google_identity(user=user, claims=claims))

        try:
            await self.db_session.commit()
        except IntegrityError:
            await self.db_session.rollback()
            return await self._recover_google_identity_after_integrity_error(claims)
        except Exception:
            await self.db_session.rollback()
            raise

        await self.db_session.refresh(user)
        return user

    async def _recover_google_identity_after_integrity_error(
        self,
        claims: VerifiedGoogleIdentityClaims,
    ) -> User:
        identity = await self._get_google_identity_by_subject(claims.provider_subject)
        if identity is not None:
            return await self._user_for_google_identity(identity, claims)

        user = await self._get_user_by_email(claims.email)
        if user is not None:
            self.db_session.add(self._build_google_identity(user=user, claims=claims))
            try:
                await self.db_session.commit()
            except IntegrityError as exc:
                await self.db_session.rollback()
                identity = await self._get_google_identity_by_subject(claims.provider_subject)
                if identity is not None:
                    return await self._user_for_google_identity(identity, claims)
                raise self._google_account_conflict_error() from exc

            await self.db_session.refresh(user)
            return user

        raise self._google_account_conflict_error()

    async def _get_google_identity_by_subject(
        self,
        provider_subject: str,
    ) -> UserIdentity | None:
        result = await self.db_session.execute(
            select(UserIdentity).where(
                func.lower(UserIdentity.provider) == GOOGLE_OAUTH_PROVIDER,
                UserIdentity.provider_subject == provider_subject,
            )
        )
        return result.scalar_one_or_none()

    async def _user_for_google_identity(
        self,
        identity: UserIdentity,
        claims: VerifiedGoogleIdentityClaims,
    ) -> User:
        user = await self._get_user_by_id(identity.user_id)
        if user is None:
            raise self._google_account_conflict_error()

        matching_email_user = await self._get_user_by_email(claims.email)
        if matching_email_user is not None and matching_email_user.id != user.id:
            raise self._google_account_conflict_error()

        return user

    @staticmethod
    def _build_google_identity(
        *,
        user: User,
        claims: VerifiedGoogleIdentityClaims,
    ) -> UserIdentity:
        return UserIdentity(
            user_id=user.id,
            provider=GOOGLE_OAUTH_PROVIDER,
            provider_subject=claims.provider_subject,
            email=claims.email,
            email_verified=claims.email_verified,
        )

    async def _is_guest_quota_exhausted(
        self,
        guest_id: str | None,
        *,
        client_ip: str | None = None,
    ) -> bool:
        analyses_used = await get_guest_analyses_used(self.redis, guest_id)
        client_analyses_used = await get_guest_analyses_used_by_key(
            self.redis,
            guest_analysis_client_key(self.settings.secret_key, client_ip),
        )
        return max(analyses_used, client_analyses_used) >= FREE_ANALYSIS_LIMIT

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

    async def _validate_and_consume_google_oauth_state(
        self,
        *,
        state: str | None,
        state_cookie: str | None,
    ) -> GoogleOAuthStatePayload:
        if not state or not state_cookie or state != state_cookie:
            raise GoogleOAuthError(
                code="google-oauth-invalid-state",
                message="Google OAuth state is invalid or expired.",
                status_code=400,
            )

        value = await self.redis.eval(
            _GET_AND_DELETE_SCRIPT,
            1,
            self._google_oauth_state_key(state),
        )
        payload = self._decode_google_oauth_state_payload(value)
        if payload is None or payload.state != state:
            raise GoogleOAuthError(
                code="google-oauth-invalid-state",
                message="Google OAuth state is invalid or expired.",
                status_code=400,
            )

        return payload

    @staticmethod
    def _encode_google_oauth_state_payload(payload: GoogleOAuthStatePayload) -> str:
        return json.dumps(
            {
                "state": payload.state,
                "created_at": payload.created_at,
            },
            separators=(",", ":"),
        )

    @classmethod
    def _decode_google_oauth_state_payload(
        cls,
        value: object,
    ) -> GoogleOAuthStatePayload | None:
        decoded_value = cls._decode_redis_value(value)
        if decoded_value is None:
            return None

        try:
            payload = json.loads(decoded_value)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict) or not isinstance(payload.get("state"), str):
            return None

        created_at = payload.get("created_at")
        return GoogleOAuthStatePayload(
            state=payload["state"],
            created_at=created_at if isinstance(created_at, int) else 0,
        )

    async def _find_google_jwks_key(self, key_id: str) -> dict[str, object] | None:
        jwks = await self._fetch_google_jwks()
        keys = jwks.get("keys")
        if not isinstance(keys, list):
            return None

        for key_data in keys:
            if isinstance(key_data, dict) and key_data.get("kid") == key_id:
                return key_data

        return None

    async def _fetch_google_jwks(self) -> dict[str, object]:
        global _google_jwks_cache

        cached_jwks = _google_jwks_cache
        if cached_jwks is not None and cached_jwks[0] > int(time()):
            return cached_jwks[1]

        try:
            async with httpx.AsyncClient(timeout=GOOGLE_OAUTH_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    GOOGLE_JWKS_URL,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GoogleOAuthError(
                code="google-oauth-unavailable",
                message="Google OAuth could not be verified right now.",
                status_code=503,
            ) from exc

        if not isinstance(payload, dict):
            raise GoogleOAuthError(
                code="google-oauth-unavailable",
                message="Google OAuth could not be verified right now.",
                status_code=503,
            )

        _google_jwks_cache = (int(time()) + GOOGLE_JWKS_CACHE_TTL_SECONDS, payload)
        return payload

    @staticmethod
    def _invalid_google_identity_error() -> GoogleOAuthError:
        return GoogleOAuthError(
            code="google-oauth-unavailable",
            message="Google OAuth identity could not be verified.",
            status_code=503,
        )

    @staticmethod
    def _google_account_conflict_error() -> GoogleOAuthError:
        return GoogleOAuthError(
            code="google-account-conflict",
            message="This Google account is linked to a different Parserly account.",
            status_code=409,
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
    def _google_oauth_state_key(state: str) -> str:
        state_hash = sha256(state.encode("utf-8")).hexdigest()
        return f"auth:google-oauth:state:{state_hash}"

    @staticmethod
    def _jwt_blocklist_key(access_token: str) -> str:
        token_hash = sha256(access_token.encode("utf-8")).hexdigest()
        return f"auth:jwt:blocklist:{token_hash}"
