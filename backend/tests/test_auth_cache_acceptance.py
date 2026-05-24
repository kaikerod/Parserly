from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.routers.auth import get_auth_service, get_auth_session_user
from app.core.authorization import (
    ALL_FEATURES_PERMISSION,
    BASIC_FEATURES_PERMISSION,
    MASTER_ADMIN_ACCESS_LEVEL,
    STANDARD_USER_ACCESS_LEVEL,
    get_session_access_profile,
)
from app.main import app
from app.services.auth_service import InvalidMagicLinkToken, MagicLinkRequestResult


class FakeAuthService:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(environment="test")
        self.logout_tokens: list[str | None] = []

    async def request_magic_link(
        self,
        email: str,
        *,
        guest_id: str | None = None,
        client_ip: str | None = None,
    ) -> MagicLinkRequestResult:
        return MagicLinkRequestResult(
            email=email,
            magic_link=f"https://parserly.test/auth/verify?token={uuid4()}",
            expires_in=900,
            requires_payment=False,
        )

    async def verify_magic_link(self, *args: object, **kwargs: object) -> None:
        raise InvalidMagicLinkToken()

    async def logout(self, access_token: str | None) -> None:
        self.logout_tokens.append(access_token)


class AccessProfileAuthService:
    def __init__(self, email: str = "person@example.com") -> None:
        self.user_id = uuid4()
        self.access_profile = get_session_access_profile(email)
        self.settings = SimpleNamespace(
            environment="test",
            google_oauth_state_cookie_name="google_oauth_state",
            auth_cookie_secure=False,
        )

    async def verify_magic_link(self, *args: object, **kwargs: object) -> SimpleNamespace:
        return self._auth_session(requires_payment=False)

    async def verify_google_oauth_callback(self, *args: object, **kwargs: object) -> SimpleNamespace:
        return self._auth_session(requires_payment=False)

    def _auth_session(self, *, requires_payment: bool) -> SimpleNamespace:
        return SimpleNamespace(
            user_id=self.user_id,
            access_token="access-token",
            expires_in=900,
            requires_payment=requires_payment,
            access_profile=self.access_profile,
        )


def override_auth_service() -> FakeAuthService:
    return FakeAuthService()


def override_access_profile_auth_service(
    email: str = "person@example.com",
) -> AccessProfileAuthService:
    return AccessProfileAuthService(email=email)


def override_auth_session_user(user: SimpleNamespace | None):
    async def _override_auth_session_user() -> SimpleNamespace | None:
        return user

    return _override_auth_session_user


def test_auth_request_link_success_and_validation_errors_are_not_cached() -> None:
    app.dependency_overrides[get_auth_service] = override_auth_service
    try:
        with TestClient(app) as client:
            success_response = client.post(
                "/api/v1/auth/request-link",
                json={"email": "person@example.com"},
            )
            validation_response = client.post("/api/v1/auth/request-link", json={})
    finally:
        app.dependency_overrides.clear()

    assert success_response.status_code == 202
    assert success_response.headers["cache-control"] == "no-store"
    assert validation_response.status_code == 422
    assert validation_response.headers["cache-control"] == "no-store"


def test_auth_verify_and_logout_errors_are_not_cached() -> None:
    app.dependency_overrides[get_auth_service] = override_auth_service
    try:
        with TestClient(app) as client:
            verify_response = client.get(f"/api/v1/auth/verify?token={uuid4()}")
            logout_response = client.get("/api/v1/auth/logout")
    finally:
        app.dependency_overrides.clear()

    assert verify_response.status_code == 401
    assert verify_response.headers["cache-control"] == "no-store"
    assert logout_response.status_code == 405
    assert logout_response.headers["cache-control"] == "no-store"


def test_auth_session_reports_valid_session_without_side_effects() -> None:
    user_id = uuid4()
    app.dependency_overrides[get_auth_session_user] = override_auth_session_user(
        SimpleNamespace(id=user_id, email="person@example.com")
    )
    try:
        with TestClient(app) as client:
            authenticated_response = client.get("/api/v1/auth/session")
    finally:
        app.dependency_overrides.clear()

    app.dependency_overrides[get_auth_session_user] = override_auth_session_user(None)
    try:
        with TestClient(app) as client:
            anonymous_response = client.get("/api/v1/auth/session")
    finally:
        app.dependency_overrides.clear()

    assert authenticated_response.status_code == 200
    assert authenticated_response.headers["cache-control"] == "no-store"
    assert authenticated_response.json() == {
        "authenticated": True,
        "user_id": str(user_id),
        "access_level": STANDARD_USER_ACCESS_LEVEL,
        "permissions": [BASIC_FEATURES_PERMISSION],
    }
    assert anonymous_response.status_code == 200
    assert anonymous_response.headers["cache-control"] == "no-store"
    assert anonymous_response.json() == {
        "authenticated": False,
        "user_id": None,
        "access_level": None,
        "permissions": [],
    }


def test_auth_session_reports_master_access_profile() -> None:
    user_id = uuid4()
    app.dependency_overrides[get_auth_session_user] = override_auth_session_user(
        SimpleNamespace(id=user_id, email="kaikevinicius789@gmail.com")
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/session")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user_id": str(user_id),
        "access_level": MASTER_ADMIN_ACCESS_LEVEL,
        "permissions": [ALL_FEATURES_PERMISSION],
    }


def test_magic_link_verify_response_includes_access_profile() -> None:
    service = override_access_profile_auth_service("kaikevinicius789@gmail.com")
    app.dependency_overrides[get_auth_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/auth/verify?token={uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "message": "Authenticated.",
        "user_id": str(service.user_id),
        "requires_payment": False,
        "access_level": MASTER_ADMIN_ACCESS_LEVEL,
        "permissions": [ALL_FEATURES_PERMISSION],
    }


def test_google_callback_response_includes_standard_access_profile() -> None:
    service = override_access_profile_auth_service("person@example.com")
    app.dependency_overrides[get_auth_service] = lambda: service
    try:
        with TestClient(app) as client:
            client.cookies.set("google_oauth_state", "state")
            response = client.get(
                "/api/v1/auth/google/callback?code=code&state=state",
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "message": "Authenticated.",
        "user_id": str(service.user_id),
        "access_level": STANDARD_USER_ACCESS_LEVEL,
        "permissions": [BASIC_FEATURES_PERMISSION],
    }
