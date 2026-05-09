from __future__ import annotations

import json
import re
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.rate_limit import (
    ConcurrentRequestLimitExceeded,
    acquire_concurrency_slot,
    release_concurrency_slot,
    retry_after_headers,
)
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
PAYMENT_STATUS_STREAM_TIMEOUT_SECONDS = 55.0
PAYMENT_STATUS_STREAM_CONCURRENCY_TTL_SECONDS = 65
WEBHOOK_MAX_PAYLOAD_BYTES = 64 * 1024
PAYMENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


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
                "message": exc.message,
            },
        ) from exc

    return CreateChargeResponse(
        billing_id=charge.billing_id,
        pix_qr_code=charge.pix_qr_code,
        pix_copy_paste=charge.pix_copy_paste,
        expires_at=charge.expires_at,
        expires_in=charge.expires_in,
        amount_cents=charge.amount_cents,
        analysis_credits=charge.analysis_credits,
    )


@router.get("/status-stream")
async def payment_status_stream(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> StreamingResponse:
    channel = f"analysis_unlocked:{current_user.id}"
    try:
        concurrency_key = await acquire_concurrency_slot(
            redis_client,
            scope="payments:status-stream",
            identifier=str(current_user.id),
            ttl_seconds=PAYMENT_STATUS_STREAM_CONCURRENCY_TTL_SECONDS,
        )
    except ConcurrentRequestLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many payment status streams.",
            headers=retry_after_headers(exc),
        ) from exc

    async def event_generator():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        try:
            yield _format_sse("connected", {"event": "connected"})
            stream_started_at = monotonic()

            while not await request.is_disconnected():
                elapsed_seconds = monotonic() - stream_started_at
                if elapsed_seconds >= PAYMENT_STATUS_STREAM_TIMEOUT_SECONDS:
                    yield _format_sse("timeout", {"event": "reconnect"})
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=15.0,
                )

                if message is None:
                    yield ": keep-alive\n\n"
                    continue

                raw_data = message.get("data")
                data = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)
                event_name = _event_name_from_payload(data)
                yield _format_sse(event_name, data)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await release_concurrency_slot(redis_client, concurrency_key)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/webhook", response_model=WebhookResponse)
async def mercadopago_webhook(
    request: Request,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    signature: Annotated[str | None, Header(alias="x-signature")] = None,
    request_id: Annotated[str | None, Header(alias="x-request-id")] = None,
) -> WebhookResponse:
    data_id = request.query_params.get("data.id")
    if not is_valid_payment_id(data_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment id.",
        )

    if not payment_service.validate_webhook_signature(signature, request_id, data_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    if request_body_too_large(request, WEBHOOK_MAX_PAYLOAD_BYTES):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload is too large.",
        )

    raw_payload = await request.body()
    if len(raw_payload) > WEBHOOK_MAX_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload is too large.",
        )

    try:
        result = await payment_service.process_webhook(raw_payload, data_id=data_id)
    except InvalidWebhookPayload as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        ) from exc
    except PaymentProviderUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "payment_provider_unavailable",
                "message": exc.message,
            },
        ) from exc

    return WebhookResponse(received=True, status=result.status)


def _event_name_from_payload(data: str) -> str:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return "message"

    if isinstance(payload, dict) and isinstance(payload.get("event"), str):
        return payload["event"]

    return "message"


def _format_sse(event_name: str, payload: dict[str, object] | str) -> str:
    data = json.dumps(payload) if isinstance(payload, dict) else payload
    data_lines = data.splitlines() or [""]
    formatted_data = "".join(f"data: {line}\n" for line in data_lines)
    return f"event: {event_name}\n{formatted_data}\n"


def is_valid_payment_id(value: str | None) -> bool:
    return bool(value and PAYMENT_ID_RE.fullmatch(value))


def request_body_too_large(request: Request, max_body_bytes: int) -> bool:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return False

    try:
        return int(content_length) > max_body_bytes
    except ValueError:
        return False
