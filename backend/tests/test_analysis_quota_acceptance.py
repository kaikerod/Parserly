from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.v1.routers.analysis as analysis_router
from app.core.quotas import FREE_ANALYSIS_LIMIT, UNLIMITED_ANALYSIS_REMAINING
from app.main import app


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def override_optional_current_user(user: SimpleNamespace):
    async def _override_optional_current_user() -> SimpleNamespace:
        return user

    return _override_optional_current_user


def test_master_admin_quota_is_unlimited_even_after_free_limit() -> None:
    user = SimpleNamespace(
        id=uuid4(),
        email="kaikevinicius789@gmail.com",
        analyses_used=FREE_ANALYSIS_LIMIT,
        paid_analysis_credits=0,
    )
    app.dependency_overrides[analysis_router.get_optional_current_user] = (
        override_optional_current_user(user)
    )
    app.dependency_overrides[analysis_router.get_redis_client] = lambda: SimpleNamespace()

    with TestClient(app) as client:
        response = client.get("/api/v1/analysis/quota")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "remaining_analyses": UNLIMITED_ANALYSIS_REMAINING,
        "payment_required": False,
        "registration_required": False,
        "unlimited_analyses": True,
        "message": None,
    }


def test_standard_user_quota_still_requires_payment_after_free_limit() -> None:
    user = SimpleNamespace(
        id=uuid4(),
        email="person@example.com",
        analyses_used=FREE_ANALYSIS_LIMIT,
        paid_analysis_credits=0,
    )
    app.dependency_overrides[analysis_router.get_optional_current_user] = (
        override_optional_current_user(user)
    )
    app.dependency_overrides[analysis_router.get_redis_client] = lambda: SimpleNamespace()

    with TestClient(app) as client:
        response = client.get("/api/v1/analysis/quota")

    payload = response.json()
    assert response.status_code == 200
    assert payload["authenticated"] is True
    assert payload["remaining_analyses"] == 0
    assert payload["payment_required"] is True
    assert payload["registration_required"] is False
    assert payload["unlimited_analyses"] is False
    assert payload["message"]
