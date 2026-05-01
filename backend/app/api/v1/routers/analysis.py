from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.analysis import AnalysisResponse
from app.services.analysis_service import (
    AIAnalysisUnavailable,
    AnalysisService,
    InvalidResumeFile,
    QuotaExceeded,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])


def get_analysis_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisService:
    return AnalysisService(db_session=db_session, settings=settings)


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    current_user: Annotated[User, Depends(get_current_user)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
    file: Annotated[UploadFile, File(...)],
) -> AnalysisResponse:
    try:
        result = await analysis_service.analyze_resume(current_user, file)
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "quota_exceeded",
                "message": "Voce atingiu o limite de 3 analises gratuitas.",
            },
        ) from exc
    except InvalidResumeFile as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "unprocessable_file",
                "reason": exc.reason,
                "message": (
                    "Nao foi possivel extrair texto do arquivo. Verifique se o PDF "
                    "nao esta protegido por senha e contem texto selecionavel."
                ),
            },
        ) from exc
    except AIAnalysisUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "analysis_unavailable",
                "message": (
                    "Servico de analise temporariamente indisponivel. "
                    "Tente novamente em alguns minutos."
                ),
            },
        ) from exc

    return AnalysisResponse(
        id=result.id,
        filename=result.filename,
        score=result.score,
        report_json=result.report,
        model_used=result.model_used,
        created_at=result.created_at,
        analyses_used=result.analyses_used,
    )
