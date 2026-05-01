from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
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

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


def get_auth_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(db_session=db_session, redis_client=redis_client, settings=settings)


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
    body: RequestMagicLinkBody,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> RequestMagicLinkResponse:
    try:
        result = await auth_service.request_magic_link(body.email)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many magic link requests for this email.",
            headers={"Retry-After": str(exc.retry_after)},
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
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    token: Annotated[UUID, Query(...)],
) -> VerifyMagicLinkResponse:
    try:
        auth_session = await auth_service.verify_magic_link(token)
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
    return VerifyMagicLinkResponse(
        message="Authenticated.",
        user_id=auth_session.user_id,
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
