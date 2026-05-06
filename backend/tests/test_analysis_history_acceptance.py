from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers.analysis import get_current_user
from app.core.database import get_db_session
from app.main import app
from app.models.analysis import Analysis


VALID_REPORT: dict[str, Any] = {
    "overall_score": 82,
    "categories": {
        "keywords": {"score": 84, "feedback": "Bom uso de termos tecnicos."},
        "formatting": {"score": 80, "feedback": "Formato legivel para ATS."},
        "structure": {"score": 81, "feedback": "Secoes bem organizadas."},
        "contact_info": {"score": 75, "feedback": "Contato suficiente."},
        "quantifiable_achievements": {
            "score": 87,
            "feedback": "Resultados mensuraveis aparecem no texto.",
        },
    },
    "recommendations": [
        {
            "priority": "high",
            "action": "Detalhar impacto por projeto.",
            "expected_impact": "Melhora a leitura de senioridade.",
        }
    ],
    "detected_role": "Engenheiro de Software",
}


class FakeExecuteResult:
    def __init__(self, *, scalar: object | None = None, scalars: list[object] | None = None) -> None:
        self.scalar = scalar
        self.scalar_items = scalars or []

    def scalar_one(self) -> object:
        return self.scalar

    def scalar_one_or_none(self) -> object | None:
        return self.scalar

    def scalars(self) -> "FakeExecuteResult":
        return self

    def all(self) -> list[object]:
        return self.scalar_items


class FakeDbSession:
    def __init__(self, results: list[FakeExecuteResult]) -> None:
        self.results = results
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeExecuteResult:
        self.statements.append(statement)
        return self.results.pop(0)


def setup_overrides(user: SimpleNamespace, db_session: FakeDbSession) -> None:
    async def override_db_session():
        yield db_session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = override_db_session


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def make_analysis(
    *,
    analysis_id: UUID,
    user_id: UUID | None,
    filename: str,
    score: int,
    created_at: datetime,
) -> Analysis:
    return Analysis(
        id=analysis_id,
        user_id=user_id,
        filename=filename,
        score=score,
        report_json=VALID_REPORT,
        model_used="test-model",
        created_at=created_at,
    )


def test_list_analyses_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/analysis")

    assert response.status_code == 401


def test_get_analysis_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/analysis/{uuid4()}")

    assert response.status_code == 401


def test_list_analyses_returns_authenticated_user_history_with_pagination() -> None:
    user_id = uuid4()
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    analyses = [
        make_analysis(
            analysis_id=uuid4(),
            user_id=user_id,
            filename="latest.pdf",
            score=91,
            created_at=now,
        ),
        make_analysis(
            analysis_id=uuid4(),
            user_id=user_id,
            filename="previous.docx",
            score=74,
            created_at=now - timedelta(days=2),
        ),
    ]
    db_session = FakeDbSession(
        [
            FakeExecuteResult(scalar=4),
            FakeExecuteResult(scalars=analyses),
        ]
    )
    setup_overrides(SimpleNamespace(id=user_id, analyses_used=2), db_session)

    with TestClient(app) as client:
        response = client.get("/api/v1/analysis?limit=2&offset=1")

    payload = response.json()
    assert response.status_code == 200
    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert payload["total"] == 4
    assert [item["filename"] for item in payload["items"]] == ["latest.pdf", "previous.docx"]
    assert payload["items"][0]["score"] == 91
    assert "report_json" not in payload["items"][0]

    list_statement = db_session.statements[1]
    assert statement_filters_user_id(list_statement, user_id)
    assert getattr(list_statement, "_limit_clause").value == 2
    assert getattr(list_statement, "_offset_clause").value == 1
    assert "analyses.created_at DESC" in str(list_statement)


def test_get_analysis_returns_saved_report_for_owner() -> None:
    user_id = uuid4()
    analysis = make_analysis(
        analysis_id=uuid4(),
        user_id=user_id,
        filename="resume.pdf",
        score=82,
        created_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
    )
    db_session = FakeDbSession([FakeExecuteResult(scalar=analysis)])
    setup_overrides(SimpleNamespace(id=user_id, analyses_used=3), db_session)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/analysis/{analysis.id}")

    payload = response.json()
    assert response.status_code == 200
    assert payload["id"] == str(analysis.id)
    assert payload["filename"] == "resume.pdf"
    assert payload["score"] == 82
    assert payload["analyses_used"] == 3
    assert payload["report_json"]["overall_score"] == 82
    assert "resume_text" not in payload
    assert statement_filters_user_id(db_session.statements[0], user_id)


def test_get_analysis_returns_404_for_missing_or_foreign_analysis() -> None:
    user_id = uuid4()
    db_session = FakeDbSession([FakeExecuteResult(scalar=None)])
    setup_overrides(SimpleNamespace(id=user_id, analyses_used=1), db_session)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/analysis/{uuid4()}")

    assert response.status_code == 404
    assert statement_filters_user_id(db_session.statements[0], user_id)


def statement_filters_user_id(statement: object, user_id: UUID) -> bool:
    criteria = getattr(statement, "_where_criteria", ())

    return any(
        str(getattr(criterion, "left", "")) == "analyses.user_id"
        and getattr(getattr(criterion, "right", None), "value", None) == user_id
        for criterion in criteria
    )
