from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.quotas import (
    FREE_ANALYSIS_LIMIT,
    GUEST_ANALYSIS_COOKIE_MAX_AGE_SECONDS,
    GUEST_ANALYSIS_COOKIE_NAME,
    GUEST_ANALYSIS_KEY_TTL_SECONDS,
    get_guest_analyses_used,
    guest_analysis_key,
    normalize_guest_id,
)
from app.core.redis import get_redis_client
from app.core.security import get_optional_current_user
from app.models.user import User
from app.schemas.analysis import AnalysisQuotaResponse, AnalysisResponse
from app.services.analysis_service import (
    AIAnalysisUnavailable,
    AnalysisService,
    InvalidResumeFile,
    QuotaExceeded,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])

PAYMENT_REQUIRED_MESSAGE = (
    "Você atingiu o limite de análises gratuitas. Pague via PIX para liberar "
    "novas análises."
)
REGISTRATION_REQUIRED_MESSAGE = (
    "Você atingiu o limite de 3 análises grátis. Cadastre-se para continuar."
)


def get_analysis_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisService:
    return AnalysisService(db_session=db_session, settings=settings)


@router.get("/quota", response_model=AnalysisQuotaResponse)
async def get_analysis_quota(
    request: Request,
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> AnalysisQuotaResponse:
    if current_user is None:
        guest_id = normalize_guest_id(request.cookies.get(GUEST_ANALYSIS_COOKIE_NAME))
        analyses_used = await get_guest_analyses_used(redis_client, guest_id)
        remaining_analyses = max(0, FREE_ANALYSIS_LIMIT - analyses_used)
        registration_required = remaining_analyses == 0
        return AnalysisQuotaResponse(
            authenticated=False,
            remaining_analyses=remaining_analyses,
            payment_required=False,
            registration_required=registration_required,
            message=REGISTRATION_REQUIRED_MESSAGE if registration_required else None,
        )

    analyses_used = normalize_analyses_used(current_user.analyses_used)
    remaining_analyses = max(0, FREE_ANALYSIS_LIMIT - analyses_used)
    payment_required = remaining_analyses == 0
    return AnalysisQuotaResponse(
        authenticated=True,
        remaining_analyses=remaining_analyses,
        payment_required=payment_required,
        registration_required=False,
        message=PAYMENT_REQUIRED_MESSAGE if payment_required else None,
    )


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    request: Request,
    response: Response,
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(...)],
) -> AnalysisResponse:
    guest_id: str | None = None
    guest_analyses_used: int | None = None

    try:
        if current_user is None:
            guest_id = get_or_create_guest_id(request)
            set_guest_analysis_cookie(response, guest_id, settings)
            guest_analyses_used = await reserve_guest_analysis(redis_client, guest_id)

        result = await analysis_service.analyze_resume(
            current_user,
            file,
            guest_analyses_used=guest_analyses_used,
        )
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "quota_exceeded",
                "message": "Voce atingiu o limite de 3 analises gratuitas.",
            },
        ) from exc
    except GuestQuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "registration_required",
                "message": (
                    "Voce atingiu o limite de 3 analises gratis. "
                    "Cadastre-se para continuar."
                ),
                "analyses_used": exc.analyses_used,
            },
        ) from exc
    except InvalidResumeFile as exc:
        await release_reserved_guest_analysis(redis_client, guest_id, guest_analyses_used)
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
        await release_reserved_guest_analysis(redis_client, guest_id, guest_analyses_used)
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
    except Exception:
        await release_reserved_guest_analysis(redis_client, guest_id, guest_analyses_used)
        raise

    return AnalysisResponse(
        id=result.id,
        filename=result.filename,
        score=result.score,
        report_json=result.report,
        model_used=result.model_used,
        created_at=result.created_at,
        analyses_used=result.analyses_used,
    )


class GuestQuotaExceeded(Exception):
    def __init__(self, analyses_used: int) -> None:
        self.analyses_used = analyses_used
        super().__init__("guest analysis quota exceeded")


def normalize_analyses_used(raw_analyses_used: object) -> int:
    try:
        return int(raw_analyses_used or 0)
    except (TypeError, ValueError):
        return 0


def get_or_create_guest_id(request: Request) -> str:
    return normalize_guest_id(request.cookies.get(GUEST_ANALYSIS_COOKIE_NAME)) or str(uuid4())


def set_guest_analysis_cookie(response: Response, guest_id: str, settings: Settings) -> None:
    response.set_cookie(
        key=GUEST_ANALYSIS_COOKIE_NAME,
        value=guest_id,
        max_age=GUEST_ANALYSIS_COOKIE_MAX_AGE_SECONDS,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )


async def reserve_guest_analysis(redis_client: Redis, guest_id: str) -> int:
    key = guest_analysis_key(guest_id)
    analyses_used = await redis_client.incr(key)
    if analyses_used == 1:
        await redis_client.expire(key, GUEST_ANALYSIS_KEY_TTL_SECONDS)

    if analyses_used > FREE_ANALYSIS_LIMIT:
        await redis_client.decr(key)
        raise GuestQuotaExceeded(analyses_used=FREE_ANALYSIS_LIMIT)

    return int(analyses_used)


async def release_reserved_guest_analysis(
    redis_client: Redis,
    guest_id: str | None,
    guest_analyses_used: int | None,
) -> None:
    if guest_id is None or guest_analyses_used is None:
        return

    await redis_client.decr(guest_analysis_key(guest_id))
