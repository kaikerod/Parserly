from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(..., ge=0, le=100)
    feedback: str = Field(..., min_length=1)


class CategoriesReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keywords: CategoryReport
    formatting: CategoryReport
    structure: CategoryReport
    contact_info: CategoryReport
    quantifiable_achievements: CategoryReport


class RecommendationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: Literal["high", "medium", "low"]
    action: str = Field(..., min_length=1)
    expected_impact: str = Field(..., min_length=1)


class AnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_score: int = Field(..., ge=0, le=100)
    categories: CategoriesReport
    recommendations: list[RecommendationReport] = Field(..., min_length=1, max_length=7)
    detected_role: str | None


class AnalysisResponse(BaseModel):
    id: UUID
    filename: str
    score: int
    report_json: AnalysisReport
    model_used: str
    created_at: datetime
    analyses_used: int


class AnalysisHistoryItem(BaseModel):
    id: UUID
    filename: str
    score: int
    created_at: datetime
    model_used: str


class AnalysisHistoryResponse(BaseModel):
    items: list[AnalysisHistoryItem]
    limit: int
    offset: int
    total: int


class AnalysisQuotaResponse(BaseModel):
    authenticated: bool
    remaining_analyses: int
    payment_required: bool
    registration_required: bool
    message: str | None = None
