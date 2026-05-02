from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.quotas import GUEST_ANALYSIS_COOKIE_NAME, normalize_guest_id
from app.core.redis import get_redis_client
from app.schemas.auth import (
    LogoutResponse,
    RequestMagicLinkBody,
    RequestMagicLinkResponse,
    VerifyMagicLinkResponse,
)
from app.services.auth_service import (
    AuthService,
    InvalidMagicLinkToken,
    RateLimitExceeded,
)
from app.services.email_service import EmailDeliveryError, EmailService

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


def get_auth_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    email_service = EmailService(settings=settings)
    return AuthService(
        db_session=db_session,
        redis_client=redis_client,
        settings=settings,
        email_service=email_service,
    )


def set_auth_cookie(response: Response, access_token: str, max_age: int) -> None:
    response.set_cookie(
        key=_settings.auth_cookie_name,
        value=access_token,
        max_age=max_age,
        path="/",
        httponly=True,
        secure=_settings.auth_cookie_secure,
        samesite=_settings.auth_cookie_samesite,
    )


def delete_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_settings.auth_cookie_name,
        path="/",
        secure=_settings.auth_cookie_secure,
        httponly=True,
        samesite=_settings.auth_cookie_samesite,
    )


@router.post(
    "/request-link",
    response_model=RequestMagicLinkResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_magic_link(
    request: Request,
    body: RequestMagicLinkBody,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> RequestMagicLinkResponse:
    guest_id = normalize_guest_id(request.cookies.get(GUEST_ANALYSIS_COOKIE_NAME))

    try:
        result = await auth_service.request_magic_link(
            body.email,
            guest_id=guest_id,
            client_ip=get_client_ip(request),
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many magic link requests for this email.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nao foi possivel enviar o link de acesso.",
        ) from exc

    magic_link = None
    if auth_service.settings.environment != "production":
        magic_link = result.magic_link

    return RequestMagicLinkResponse(
        message="Magic link sent.",
        expires_in=result.expires_in,
        magic_link=magic_link,
    )


@router.get("/verify", response_model=VerifyMagicLinkResponse)
async def verify_magic_link(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    token: Annotated[UUID, Query(...)],
) -> VerifyMagicLinkResponse:
    guest_id = normalize_guest_id(request.cookies.get(GUEST_ANALYSIS_COOKIE_NAME))

    try:
        auth_session = await auth_service.verify_magic_link(token, guest_id=guest_id)
    except InvalidMagicLinkToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link token.",
        ) from exc

    set_auth_cookie(
        response=response,
        access_token=auth_session.access_token,
        max_age=auth_session.expires_in,
    )
    request.state.user_id = str(auth_session.user_id)
    return VerifyMagicLinkResponse(
        message="Authenticated.",
        user_id=auth_session.user_id,
        requires_payment=auth_session.requires_payment,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    access_token: Annotated[str | None, Cookie(alias=_settings.auth_cookie_name)] = None,
) -> LogoutResponse:
    await auth_service.logout(access_token)
    delete_auth_cookie(response)
    return LogoutResponse(message="Logged out.")


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client is None:
        return None

    return request.client.host
