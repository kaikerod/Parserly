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

    auth_service = AuthService(
        db_session=db_session,
        redis_client=redis_client,
        settings=settings,
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
