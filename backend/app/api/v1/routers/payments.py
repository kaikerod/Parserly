from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.redis import get_redis_client
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.payment import CreateChargeResponse, WebhookResponse
from app.services.payment_service import (
    InvalidWebhookPayload,
    PaymentProviderUnavailable,
    PaymentRateLimitExceeded,
    PaymentService,
)

router = APIRouter(prefix="/payments", tags=["payments"])


def get_payment_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PaymentService:
    return PaymentService(
        db_session=db_session,
        redis_client=redis_client,
        settings=settings,
    )


@router.post(
    "/create-charge",
    response_model=CreateChargeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_charge(
    current_user: Annotated[User, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> CreateChargeResponse:
    try:
        charge = await payment_service.create_charge(current_user)
    except PaymentRateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many payment requests for this user.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except PaymentProviderUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "payment_provider_unavailable",
                "message": "Nao foi possivel gerar a cobranca PIX no momento.",
            },
        ) from exc

    return CreateChargeResponse(
        billing_id=charge.billing_id,
        pix_qr_code=charge.pix_qr_code,
        pix_copy_paste=charge.pix_copy_paste,
        expires_at=charge.expires_at,
        expires_in=charge.expires_in,
        amount_cents=charge.amount_cents,
    )


@router.post("/webhook", response_model=WebhookResponse)
async def abacatepay_webhook(
    request: Request,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    signature: Annotated[str | None, Header(alias="X-Abacatepay-Signature")] = None,
) -> WebhookResponse:
    raw_payload = await request.body()
    if not payment_service.validate_webhook_signature(raw_payload, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    try:
        result = await payment_service.process_webhook(raw_payload)
    except InvalidWebhookPayload as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        ) from exc

    return WebhookResponse(received=True, status=result.status)
