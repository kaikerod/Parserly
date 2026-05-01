from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.redis import get_redis_client
from app.core.security import get_optional_current_user
from app.models.user import User
from app.schemas.analysis import AnalysisResponse
from app.services.analysis_service import (
    AIAnalysisUnavailable,
    AnalysisService,
    FREE_ANALYSIS_LIMIT,
    InvalidResumeFile,
    QuotaExceeded,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])
GUEST_ANALYSIS_COOKIE_NAME = "parserly_guest_id"
GUEST_ANALYSIS_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180
GUEST_ANALYSIS_KEY_TTL_SECONDS = GUEST_ANALYSIS_COOKIE_MAX_AGE_SECONDS


def get_analysis_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisService:
    return AnalysisService(db_session=db_session, settings=settings)


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


def get_or_create_guest_id(request: Request) -> str:
    raw_guest_id = request.cookies.get(GUEST_ANALYSIS_COOKIE_NAME)
    if raw_guest_id:
        try:
            return str(UUID(raw_guest_id))
        except ValueError:
            pass

    return str(uuid4())


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


def guest_analysis_key(guest_id: str) -> str:
    return f"analysis:guest:{guest_id}:used"
