from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import (
    DatabaseSchemaError,
    _validate_alembic_revision,
    _validate_required_database_columns,
    app,
)


async def healthy_check() -> None:
    return None


async def failing_check() -> None:
    raise RuntimeError("dependency unavailable")


def test_health_endpoint_reports_ok_without_caching(monkeypatch) -> None:
    monkeypatch.setattr("app.main._check_database", healthy_check)
    monkeypatch.setattr("app.main._check_redis", healthy_check)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "ok"


def test_health_endpoint_reports_degraded_dependency(monkeypatch) -> None:
    monkeypatch.setattr("app.main._check_database", failing_check)
    monkeypatch.setattr("app.main._check_redis", healthy_check)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    payload = response.json()
    assert response.status_code == 503
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"] == {
        "ok": False,
        "error": "RuntimeError",
        "detail": "dependency unavailable",
    }
    assert payload["checks"]["redis"] == {"ok": True}


def test_health_schema_validation_accepts_current_revision_and_required_columns() -> None:
    _validate_alembic_revision(["20260522_0003"])
    _validate_required_database_columns(
        [
            ("users", "id"),
            ("users", "email"),
            ("users", "analyses_used"),
            ("users", "paid_analysis_credits"),
            ("user_identities", "id"),
            ("user_identities", "user_id"),
            ("user_identities", "provider"),
            ("user_identities", "provider_subject"),
            ("user_identities", "email"),
            ("user_identities", "email_verified"),
            ("analyses", "id"),
            ("analyses", "user_id"),
            ("analyses", "filename"),
            ("analyses", "report_json"),
            ("analyses", "model_used"),
            ("payments", "id"),
            ("payments", "user_id"),
            ("payments", "billing_id"),
            ("payments", "amount_cents"),
            ("payments", "status"),
        ]
    )


def test_health_schema_validation_rejects_outdated_migration_revision() -> None:
    try:
        _validate_alembic_revision(["20260503_0001"])
    except DatabaseSchemaError as exc:
        assert "Expected Alembic revision 20260522_0003" in str(exc)
    else:
        raise AssertionError("Expected DatabaseSchemaError")


def test_health_schema_validation_rejects_missing_required_columns() -> None:
    try:
        _validate_required_database_columns(
            [
                ("users", "id"),
                ("users", "email"),
                ("users", "analyses_used"),
            ]
        )
    except DatabaseSchemaError as exc:
        assert "users.paid_analysis_credits" in str(exc)
        assert "user_identities.provider_subject" in str(exc)
        assert "analyses.report_json" in str(exc)
        assert "payments.billing_id" in str(exc)
    else:
        raise AssertionError("Expected DatabaseSchemaError")
