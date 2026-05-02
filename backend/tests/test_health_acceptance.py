from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


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
    assert payload["checks"]["database"] == {"ok": False, "error": "RuntimeError"}
    assert payload["checks"]["redis"] == {"ok": True}
