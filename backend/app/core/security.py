from __future__ import annotations

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.redis import get_redis_client
from app.models.user import User
from app.services.auth_service import AuthService, JWT_ALGORITHM
from app.services.email_service import EmailService


async def get_current_user(
    request: Request,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    access_token = request.cookies.get(settings.auth_cookie_name)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    user = await _get_user_from_access_token(
        access_token=access_token,
        db_session=db_session,
        redis_client=redis_client,
        settings=settings,
    )
    request.state.user_id = str(user.id)
    return user


async def resolve_current_user_from_token(
    access_token: str | None,
    db_session: AsyncSession,
    redis_client: Redis,
    settings: Settings,
) -> User | None:
    if not access_token:
        return None

    try:
        return await _get_user_from_access_token(
            access_token=access_token,
            db_session=db_session,
            redis_client=redis_client,
            settings=settings,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


async def get_optional_current_user(
    request: Request,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User | None:
    access_token = request.cookies.get(settings.auth_cookie_name)
    if not access_token:
        return None

    user = await _get_user_from_access_token(
        access_token=access_token,
        db_session=db_session,
        redis_client=redis_client,
        settings=settings,
    )
    request.state.user_id = str(user.id)
    return user


async def _get_user_from_access_token(
    access_token: str,
    db_session: AsyncSession,
    redis_client: Redis,
    settings: Settings,
) -> User:
    auth_service = AuthService(
        db_session=db_session,
        redis_client=redis_client,
        settings=settings,
        email_service=EmailService(settings=settings),
    )
    if await auth_service.is_access_token_blocklisted(access_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is no longer valid.",
        )

    try:
        payload = jwt.decode(
            access_token,
            settings.secret_key,
            algorithms=[JWT_ALGORITHM],
        )
        user_id = UUID(str(payload["user_id"]))
    except (KeyError, ValueError, jwt.InvalidTokenError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc

    result = await db_session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user was not found.",
        )

    return user
