from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.utils import base64url_encode
from sqlalchemy.exc import IntegrityError

from app.api.v1.routers.auth import get_auth_service
from app.core.config import Settings
from app.main import app
from app.models.user import User
from app.models.user_identity import UserIdentity
from app.services.auth_service import (
    AuthService,
    GoogleOAuthError,
    GoogleOAuthStartResult,
    VerifiedGoogleIdentityClaims,
)


class GoogleOAuthRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.expirations[key] = ex

    async def eval(
        self,
        script: str,
        key_count: int,
        key: str,
        *args: object,
    ) -> str | None:
        value = self.store.get(key)
        if value is not None:
            del self.store[key]
        return value

    async def exists(self, key: str) -> bool:
        return key in self.store


class FakeEmailService:
    pass


def google_settings() -> Settings:
    return Settings(
        environment="test",
        secret_key="google-oauth-test-secret-with-32-bytes",
        app_url="https://parserly.test",
        auth_cookie_secure=False,
        google_client_id="google-client-id.apps.googleusercontent.com",
        google_client_secret="google-client-secret",
        google_oauth_redirect_uri="https://parserly.test/auth/google/callback",
        google_oauth_state_ttl_seconds=600,
    )


def make_auth_service(redis: GoogleOAuthRedis | None = None) -> AuthService:
    return AuthService(
        db_session=object(),  # type: ignore[arg-type]
        redis_client=redis or GoogleOAuthRedis(),  # type: ignore[arg-type]
        settings=google_settings(),
        email_service=FakeEmailService(),  # type: ignore[arg-type]
    )


def test_google_start_creates_state_record_and_authorization_url() -> None:
    redis = GoogleOAuthRedis()
    service = make_auth_service(redis)

    result = asyncio.run(service.create_google_authorization_url())
    parsed_url = urlparse(result.authorization_url)
    query = parse_qs(parsed_url.query)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "accounts.google.com"
    assert parsed_url.path == "/o/oauth2/v2/auth"
    assert query["scope"] == ["openid email profile"]
    assert query["client_id"] == [service.settings.google_client_id]
    assert query["redirect_uri"] == [service.settings.google_oauth_redirect_uri]
    assert query["state"] == [result.state]
    assert len(result.state) >= 48
    assert redis.store[service._google_oauth_state_key(result.state)]
    assert redis.expirations[service._google_oauth_state_key(result.state)] == 600


class StartRouteAuthService:
    settings = google_settings()

    async def create_google_authorization_url(self) -> GoogleOAuthStartResult:
        return GoogleOAuthStartResult(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth?state=state-token",
            state="state-token",
            cookie_name=self.settings.google_oauth_state_cookie_name,
            expires_in=600,
        )


def override_start_route_auth_service() -> StartRouteAuthService:
    return StartRouteAuthService()


def test_google_start_route_sets_httponly_state_cookie() -> None:
    app.dependency_overrides[get_auth_service] = override_start_route_auth_service
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/google/start", follow_redirects=False)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://accounts.google.com/")
    assert "google_oauth_state=state-token" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Max-Age=600" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]


def test_google_callback_rejects_state_mismatch() -> None:
    service = make_auth_service()

    with pytest.raises(GoogleOAuthError) as exc_info:
        asyncio.run(
            service.verify_google_oauth_callback(
                code="authorization-code",
                state="query-state",
                state_cookie="cookie-state",
            )
        )

    assert exc_info.value.code == "google-oauth-invalid-state"


class CallbackAuthService(AuthService):
    def __init__(self, redis: GoogleOAuthRedis) -> None:
        self.user_id = uuid4()
        super().__init__(
            db_session=object(),  # type: ignore[arg-type]
            redis_client=redis,  # type: ignore[arg-type]
            settings=google_settings(),
            email_service=FakeEmailService(),  # type: ignore[arg-type]
        )

    async def exchange_google_authorization_code(self, code: str):
        return SimpleNamespace(id_token="id-token")

    async def verify_google_id_token(self, id_token: str) -> VerifiedGoogleIdentityClaims:
        return VerifiedGoogleIdentityClaims(
            provider_subject="google-subject",
            email="person@example.com",
            email_verified=True,
        )

    async def _resolve_google_identity(self, claims: VerifiedGoogleIdentityClaims) -> User:
        return User(
            id=self.user_id,
            email=claims.email,
            analyses_used=0,
            paid_analysis_credits=0,
        )


def test_google_callback_consumes_state_once_and_rejects_replay() -> None:
    redis = GoogleOAuthRedis()
    service = CallbackAuthService(redis)
    state = "single-use-state"
    redis.store[service._google_oauth_state_key(state)] = service._encode_google_oauth_state_payload(
        SimpleNamespace(state=state, created_at=1)  # type: ignore[arg-type]
    )

    session = asyncio.run(
        service.verify_google_oauth_callback(
            code="authorization-code",
            state=state,
            state_cookie=state,
        )
    )

    assert session.user_id == service.user_id
    assert service._google_oauth_state_key(state) not in redis.store

    with pytest.raises(GoogleOAuthError) as exc_info:
        asyncio.run(
            service.verify_google_oauth_callback(
                code="authorization-code",
                state=state,
                state_cookie=state,
            )
        )

    assert exc_info.value.code == "google-oauth-invalid-state"


def test_google_callback_denied_consent_uses_stable_error_code() -> None:
    service = make_auth_service()

    with pytest.raises(GoogleOAuthError) as exc_info:
        asyncio.run(
            service.verify_google_oauth_callback(
                code=None,
                state="state",
                state_cookie="state",
                oauth_error="access_denied",
            )
        )

    assert exc_info.value.code == "google-oauth-denied"


def test_google_id_token_verification_accepts_valid_google_claims() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {"keys": [rsa_public_jwk(private_key, kid="google-key")]}
    service = make_auth_service()

    async def fetch_jwks() -> dict[str, object]:
        return jwks

    service._fetch_google_jwks = fetch_jwks  # type: ignore[method-assign]
    id_token = jwt.encode(
        {
            "iss": "https://accounts.google.com",
            "aud": service.settings.google_client_id,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "sub": "google-subject",
            "email": "Person@Example.com",
            "email_verified": True,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "google-key"},
    )

    claims = asyncio.run(service.verify_google_id_token(id_token))

    assert claims == VerifiedGoogleIdentityClaims(
        provider_subject="google-subject",
        email="person@example.com",
        email_verified=True,
    )


def test_google_id_token_verification_rejects_unverified_email() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    service = make_auth_service()

    async def fetch_jwks() -> dict[str, object]:
        return {"keys": [rsa_public_jwk(private_key, kid="google-key")]}

    service._fetch_google_jwks = fetch_jwks  # type: ignore[method-assign]
    id_token = jwt.encode(
        {
            "iss": "https://accounts.google.com",
            "aud": service.settings.google_client_id,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "sub": "google-subject",
            "email": "person@example.com",
            "email_verified": False,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "google-key"},
    )

    with pytest.raises(GoogleOAuthError) as exc_info:
        asyncio.run(service.verify_google_id_token(id_token))

    assert exc_info.value.code == "google-email-unverified"


class InMemoryIdentityStore:
    def __init__(self) -> None:
        self.users_by_id: dict[UUID, User] = {}
        self.users_by_email: dict[str, User] = {}
        self.identities_by_subject: dict[str, UserIdentity] = {}


class InMemoryDbSession:
    def __init__(self, store: InMemoryIdentityStore) -> None:
        self.store = store
        self.pending: list[object] = []

    def add(self, value: object) -> None:
        self.pending.append(value)

    async def flush(self) -> None:
        for value in self.pending:
            if isinstance(value, User) and value.id is None:
                value.id = uuid4()

    async def commit(self) -> None:
        for value in self.pending:
            if isinstance(value, User):
                key = value.email.lower()
                if key in self.store.users_by_email:
                    raise IntegrityError("duplicate user", {}, Exception("duplicate user"))
                self.store.users_by_id[value.id] = value
                self.store.users_by_email[key] = value
            elif isinstance(value, UserIdentity):
                key = value.provider_subject
                if key in self.store.identities_by_subject:
                    raise IntegrityError("duplicate identity", {}, Exception("duplicate identity"))
                self.store.identities_by_subject[key] = value

        self.pending.clear()

    async def rollback(self) -> None:
        self.pending.clear()

    async def refresh(self, value: object) -> None:
        return None


class InMemoryGoogleAuthService(AuthService):
    def __init__(self, store: InMemoryIdentityStore) -> None:
        self.store = store
        super().__init__(
            db_session=InMemoryDbSession(store),  # type: ignore[arg-type]
            redis_client=GoogleOAuthRedis(),  # type: ignore[arg-type]
            settings=google_settings(),
            email_service=FakeEmailService(),  # type: ignore[arg-type]
        )

    async def _get_user_by_email(self, email: str) -> User | None:
        return self.store.users_by_email.get(email.lower())

    async def _get_user_by_id(self, user_id: UUID) -> User | None:
        return self.store.users_by_id.get(user_id)

    async def _get_google_identity_by_subject(
        self,
        provider_subject: str,
    ) -> UserIdentity | None:
        return self.store.identities_by_subject.get(provider_subject)


def test_google_identity_resolution_creates_new_user_and_identity() -> None:
    store = InMemoryIdentityStore()
    service = InMemoryGoogleAuthService(store)

    user = asyncio.run(
        service._resolve_google_identity(
            VerifiedGoogleIdentityClaims(
                provider_subject="new-google-subject",
                email="new@example.com",
                email_verified=True,
            )
        )
    )

    assert user.email == "new@example.com"
    assert store.users_by_email["new@example.com"].id == user.id
    identity = store.identities_by_subject["new-google-subject"]
    assert identity.user_id == user.id
    assert identity.provider == "google"
    assert identity.email_verified is True


def test_google_identity_resolution_links_existing_magic_link_user_without_replacing_state() -> None:
    store = InMemoryIdentityStore()
    user = User(
        id=uuid4(),
        email="person@example.com",
        analyses_used=2,
        paid_analysis_credits=5,
    )
    store.users_by_id[user.id] = user
    store.users_by_email[user.email] = user
    service = InMemoryGoogleAuthService(store)

    resolved_user = asyncio.run(
        service._resolve_google_identity(
            VerifiedGoogleIdentityClaims(
                provider_subject="linked-google-subject",
                email="person@example.com",
                email_verified=True,
            )
        )
    )

    assert resolved_user.id == user.id
    assert resolved_user.analyses_used == 2
    assert resolved_user.paid_analysis_credits == 5
    assert store.identities_by_subject["linked-google-subject"].user_id == user.id


def test_google_identity_resolution_rejects_unverified_email_without_modifying_accounts() -> None:
    store = InMemoryIdentityStore()
    service = InMemoryGoogleAuthService(store)

    with pytest.raises(GoogleOAuthError) as exc_info:
        asyncio.run(
            service._resolve_google_identity(
                VerifiedGoogleIdentityClaims(
                    provider_subject="unverified-google-subject",
                    email="person@example.com",
                    email_verified=False,
                )
            )
        )

    assert exc_info.value.code == "google-email-unverified"
    assert store.users_by_email == {}
    assert store.identities_by_subject == {}


def test_google_identity_resolution_rejects_cross_user_subject_collision() -> None:
    store = InMemoryIdentityStore()
    linked_user = User(id=uuid4(), email="linked@example.com")
    matching_email_user = User(id=uuid4(), email="person@example.com")
    store.users_by_id[linked_user.id] = linked_user
    store.users_by_id[matching_email_user.id] = matching_email_user
    store.users_by_email[linked_user.email] = linked_user
    store.users_by_email[matching_email_user.email] = matching_email_user
    store.identities_by_subject["google-subject"] = UserIdentity(
        user_id=linked_user.id,
        provider="google",
        provider_subject="google-subject",
        email="linked@example.com",
        email_verified=True,
    )
    service = InMemoryGoogleAuthService(store)

    with pytest.raises(GoogleOAuthError) as exc_info:
        asyncio.run(
            service._resolve_google_identity(
                VerifiedGoogleIdentityClaims(
                    provider_subject="google-subject",
                    email="person@example.com",
                    email_verified=True,
                )
            )
        )

    assert exc_info.value.code == "google-account-conflict"
    assert len(store.identities_by_subject) == 1


def rsa_public_jwk(private_key, *, kid: str) -> dict[str, object]:
    public_numbers = private_key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "kid": kid,
        "alg": "RS256",
        "n": base64url_uint(public_numbers.n),
        "e": base64url_uint(public_numbers.e),
    }


def base64url_uint(value: int) -> str:
    return base64url_encode(value.to_bytes((value.bit_length() + 7) // 8, "big")).decode()
