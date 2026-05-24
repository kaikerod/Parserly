from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.quotas import (
    FREE_ANALYSIS_LIMIT,
    GUEST_ANALYSIS_COOKIE_MAX_AGE_SECONDS,
    GUEST_ANALYSIS_COOKIE_NAME,
    GUEST_ANALYSIS_KEY_TTL_SECONDS,
    get_free_analyses_remaining,
    get_guest_analyses_used_by_key,
    get_guest_analyses_used,
    get_user_remaining_analyses,
    guest_analysis_client_key,
    guest_analysis_key,
    normalize_analysis_count,
    normalize_guest_id,
    user_has_unlimited_analyses,
    user_requires_payment,
)
from app.core.rate_limit import (
    ConcurrentRequestLimitExceeded,
    RateLimitExceeded,
    acquire_concurrency_slot,
    client_ip_from_request,
    enforce_rate_limit,
    release_concurrency_slot,
    retry_after_headers,
)
from app.core.redis import get_redis_client
from app.core.security import get_current_user, get_optional_current_user
from app.models.analysis import Analysis
from app.models.user import User
from app.schemas.analysis import (
    AnalysisHistoryItem,
    AnalysisHistoryResponse,
    AnalysisQuotaResponse,
    AnalysisReport,
    AnalysisResponse,
)
from app.services.analysis_service import (
    AIAnalysisUnavailable,
    AnalysisService,
    InvalidResumeFile,
    QuotaExceeded,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])
ANALYSIS_RATE_LIMIT_SECONDS = 60 * 60
AUTH_ANALYSIS_RATE_LIMIT_MAX_REQUESTS = 10
GUEST_ANALYSIS_IP_RATE_LIMIT_MAX_REQUESTS = 5
ANALYSIS_CONCURRENCY_TTL_SECONDS = 90

PAYMENT_REQUIRED_MESSAGE = (
    "Você atingiu o limite de análises gratuitas. Pague via PIX para liberar "
    "novas análises."
)
REGISTRATION_REQUIRED_MESSAGE = (
    "Você atingiu o limite gratuito. Cadastre-se para continuar."
)


def get_analysis_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisService:
    return AnalysisService(db_session=db_session, settings=settings)


@router.get("", response_model=AnalysisHistoryResponse)
async def list_analyses(
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnalysisHistoryResponse:
    total_result = await db_session.execute(
        select(func.count())
        .select_from(Analysis)
        .where(Analysis.user_id == current_user.id)
    )
    total = int(total_result.scalar_one())

    result = await db_session.execute(
        select(Analysis)
        .where(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(limit)
        .offset(offset)
    )
    analyses = result.scalars().all()

    return AnalysisHistoryResponse(
        items=[analysis_history_item(analysis) for analysis in analyses],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get("/quota", response_model=AnalysisQuotaResponse)
async def get_analysis_quota(
    request: Request,
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisQuotaResponse:
    if current_user is None:
        guest_id = normalize_guest_id(request.cookies.get(GUEST_ANALYSIS_COOKIE_NAME))
        analyses_used = await get_guest_quota_analyses_used(
            redis_client=redis_client,
            request=request,
            guest_id=guest_id,
            settings=settings,
        )
        remaining_analyses = get_free_analyses_remaining(analyses_used)
        registration_required = remaining_analyses == 0
        return AnalysisQuotaResponse(
            authenticated=False,
            remaining_analyses=remaining_analyses,
            payment_required=False,
            registration_required=registration_required,
            unlimited_analyses=False,
            message=REGISTRATION_REQUIRED_MESSAGE if registration_required else None,
        )

    remaining_analyses = get_user_remaining_analyses(current_user)
    payment_required = user_requires_payment(current_user)
    unlimited_analyses = user_has_unlimited_analyses(current_user)
    return AnalysisQuotaResponse(
        authenticated=True,
        remaining_analyses=remaining_analyses,
        payment_required=payment_required,
        registration_required=False,
        unlimited_analyses=unlimited_analyses,
        message=PAYMENT_REQUIRED_MESSAGE if payment_required else None,
    )


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AnalysisResponse:
    result = await db_session.execute(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis was not found.",
        )

    return analysis_response(
        analysis,
        analyses_used=normalize_analyses_used(current_user.analyses_used),
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
    guest_quota_keys: list[str] = []
    concurrency_key: str | None = None

    try:
        if current_user is None:
            guest_id = get_or_create_guest_id(request)
            await enforce_analysis_rate_limits(
                request=request,
                redis_client=redis_client,
                scope="guest",
                identifier=client_ip_from_request(request),
                max_requests=GUEST_ANALYSIS_IP_RATE_LIMIT_MAX_REQUESTS,
            )
            concurrency_key = await acquire_concurrency_slot(
                redis_client,
                scope="analysis:create",
                identifier=f"guest:{client_ip_from_request(request)}",
                ttl_seconds=ANALYSIS_CONCURRENCY_TTL_SECONDS,
            )
            set_guest_analysis_cookie(response, guest_id, settings)
            guest_quota_keys = guest_analysis_quota_keys(
                request=request,
                settings=settings,
                guest_id=guest_id,
            )
            guest_analyses_used = await reserve_guest_analysis(
                redis_client,
                guest_quota_keys,
            )
        else:
            unlimited_analyses = user_has_unlimited_analyses(current_user)
            if not unlimited_analyses:
                await enforce_analysis_rate_limits(
                    request=request,
                    redis_client=redis_client,
                    scope="user",
                    identifier=str(current_user.id),
                    max_requests=AUTH_ANALYSIS_RATE_LIMIT_MAX_REQUESTS,
                )
            concurrency_key = await acquire_concurrency_slot(
                redis_client,
                scope="analysis:create",
                identifier=f"user:{current_user.id}",
                ttl_seconds=ANALYSIS_CONCURRENCY_TTL_SECONDS,
            )

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
                "message": "Voce atingiu o limite gratuito.",
            },
        ) from exc
    except GuestQuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "registration_required",
                "message": (
                    "Voce atingiu o limite gratuito. "
                    "Cadastre-se para continuar."
                ),
                "analyses_used": exc.analyses_used,
            },
        ) from exc
    except InvalidResumeFile as exc:
        await release_reserved_guest_analysis(
            redis_client,
            guest_quota_keys,
            guest_analyses_used,
        )
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
        await release_reserved_guest_analysis(
            redis_client,
            guest_quota_keys,
            guest_analyses_used,
        )
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
    except (RateLimitExceeded, ConcurrentRequestLimitExceeded) as exc:
        await release_reserved_guest_analysis(
            redis_client,
            guest_quota_keys,
            guest_analyses_used,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many analysis requests.",
            headers=retry_after_headers(exc),
        ) from exc
    except Exception:
        await release_reserved_guest_analysis(
            redis_client,
            guest_quota_keys,
            guest_analyses_used,
        )
        raise
    finally:
        try:
            await release_concurrency_slot(redis_client, concurrency_key)
        except Exception:
            pass

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
    return normalize_analysis_count(raw_analyses_used)


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


async def reserve_guest_analysis(redis_client: Redis, quota_keys: list[str] | str) -> int:
    keys = normalize_guest_quota_keys(quota_keys)
    analyses_used_by_key: list[int] = []

    for key in keys:
        analyses_used = await redis_client.incr(key)
        if analyses_used == 1:
            await redis_client.expire(key, GUEST_ANALYSIS_KEY_TTL_SECONDS)
        analyses_used_by_key.append(int(analyses_used))

    analyses_used = max(analyses_used_by_key)
    if analyses_used > FREE_ANALYSIS_LIMIT:
        for key in keys:
            await redis_client.decr(key)
        raise GuestQuotaExceeded(analyses_used=FREE_ANALYSIS_LIMIT)

    return int(analyses_used)


async def release_reserved_guest_analysis(
    redis_client: Redis,
    quota_keys: list[str] | str | None,
    guest_analyses_used: int | None,
) -> None:
    if not quota_keys or guest_analyses_used is None:
        return

    for key in normalize_guest_quota_keys(quota_keys):
        await redis_client.decr(key)


async def get_guest_quota_analyses_used(
    *,
    redis_client: Redis,
    request: Request,
    guest_id: str | None,
    settings: Settings,
) -> int:
    guest_used = await get_guest_analyses_used(redis_client, guest_id)
    client_used = await get_guest_analyses_used_by_key(
        redis_client,
        guest_analysis_client_quota_key(request=request, settings=settings),
    )
    return max(guest_used, client_used)


def guest_analysis_quota_keys(
    *,
    request: Request,
    settings: Settings,
    guest_id: str,
) -> list[str]:
    keys = [guest_analysis_key(guest_id)]
    client_key = guest_analysis_client_quota_key(request=request, settings=settings)
    if client_key is not None:
        keys.append(client_key)
    return normalize_guest_quota_keys(keys)


def guest_analysis_client_quota_key(
    *,
    request: Request,
    settings: Settings,
) -> str | None:
    return guest_analysis_client_key(
        settings.secret_key,
        client_ip_from_request(request),
    )


def normalize_guest_quota_keys(quota_keys: list[str] | str) -> list[str]:
    if isinstance(quota_keys, str):
        guest_id = normalize_guest_id(quota_keys)
        raw_keys = [guest_analysis_key(guest_id) if guest_id is not None else quota_keys]
    else:
        raw_keys = quota_keys

    deduplicated_keys = list(dict.fromkeys(key for key in raw_keys if key))
    if not deduplicated_keys:
        raise ValueError("at least one guest quota key is required")
    return deduplicated_keys


async def enforce_analysis_rate_limits(
    *,
    request: Request,
    redis_client: Redis,
    scope: str,
    identifier: str,
    max_requests: int,
) -> None:
    await enforce_rate_limit(
        redis_client,
        scope=f"analysis:create:{scope}",
        identifier=identifier,
        max_requests=max_requests,
        window_seconds=ANALYSIS_RATE_LIMIT_SECONDS,
    )

    client_ip = client_ip_from_request(request)
    if scope != "guest" and client_ip:
        await enforce_rate_limit(
            redis_client,
            scope="analysis:create:ip",
            identifier=client_ip,
            max_requests=AUTH_ANALYSIS_RATE_LIMIT_MAX_REQUESTS * 2,
            window_seconds=ANALYSIS_RATE_LIMIT_SECONDS,
        )


def analysis_history_item(analysis: Analysis) -> AnalysisHistoryItem:
    return AnalysisHistoryItem(
        id=analysis.id,
        filename=analysis.filename,
        score=analysis.score or 0,
        created_at=analysis.created_at,
        model_used=analysis.model_used,
    )


def analysis_response(analysis: Analysis, *, analyses_used: int) -> AnalysisResponse:
    return AnalysisResponse(
        id=analysis.id,
        filename=analysis.filename,
        score=analysis.score or 0,
        report_json=AnalysisReport.model_validate(analysis.report_json),
        model_used=analysis.model_used,
        created_at=analysis.created_at,
        analyses_used=analyses_used,
    )
