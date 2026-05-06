from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from app.core.config import Settings
from app.core.quotas import FREE_ANALYSIS_LIMIT, guest_analysis_key
from app.api.v1.routers.analysis import GuestQuotaExceeded, release_reserved_guest_analysis
from app.api.v1.routers.analysis import reserve_guest_analysis
from app.services.auth_service import AuthService, InvalidMagicLinkToken, MagicLinkPayload
from app.services.payment_service import (
    InvalidWebhookPayload,
    PaymentCharge,
    PaymentService,
    WebhookProcessResult,
)


class GuestQuotaRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def decr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) - 1
        return self.values[key]

    async def expire(self, key: str, ttl: int) -> None:
        self.expirations[key] = ttl


def test_guest_quota_reservation_blocks_fourth_analysis_and_rolls_back() -> None:
    redis = GuestQuotaRedis()
    guest_id = str(uuid4())

    assert asyncio.run(reserve_guest_analysis(redis, guest_id)) == 1  # type: ignore[arg-type]
    assert asyncio.run(reserve_guest_analysis(redis, guest_id)) == 2  # type: ignore[arg-type]
    assert asyncio.run(reserve_guest_analysis(redis, guest_id)) == 3  # type: ignore[arg-type]

    with pytest.raises(GuestQuotaExceeded) as exc_info:
        asyncio.run(reserve_guest_analysis(redis, guest_id))  # type: ignore[arg-type]

    assert exc_info.value.analyses_used == FREE_ANALYSIS_LIMIT
    assert redis.values[guest_analysis_key(guest_id)] == FREE_ANALYSIS_LIMIT
    assert guest_analysis_key(guest_id) in redis.expirations


def test_guest_quota_reservation_is_released_after_processing_failure() -> None:
    redis = GuestQuotaRedis()
    guest_id = str(uuid4())
    used = asyncio.run(reserve_guest_analysis(redis, guest_id))  # type: ignore[arg-type]

    asyncio.run(
        release_reserved_guest_analysis(redis, guest_id, used)  # type: ignore[arg-type]
    )

    assert redis.values[guest_analysis_key(guest_id)] == 0


class MagicLinkRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def eval(self, script: str, key_count: int, key: str, *args: object) -> str | None:
        value = self.store.get(key)
        if value is not None:
            del self.store[key]
        return value


class FakeAuthService(AuthService):
    def __init__(self, redis: MagicLinkRedis) -> None:
        self.test_user_id = uuid4()
        super().__init__(
            db_session=object(),  # type: ignore[arg-type]
            redis_client=redis,  # type: ignore[arg-type]
            settings=Settings(
                environment="test",
                secret_key="magic-link-test-secret-with-32-bytes-minimum",
                app_url="https://parserly.test",
            ),
            email_service=object(),  # type: ignore[arg-type]
        )

    async def _get_or_create_user(self, email: str) -> SimpleNamespace:
        return SimpleNamespace(id=self.test_user_id, email=email, analyses_used=0)

    async def _mark_user_free_quota_exhausted(self, user: SimpleNamespace) -> None:
        user.analyses_used = FREE_ANALYSIS_LIMIT


def test_magic_link_verify_consumes_token_and_rejects_reuse() -> None:
    redis = MagicLinkRedis()
    service = FakeAuthService(redis)
    token = uuid4()
    redis.store[service._magic_link_key(token)] = service._encode_magic_link_payload(
        MagicLinkPayload(email="Pessoa@Example.com", requires_payment=False)
    )

    session = asyncio.run(service.verify_magic_link(token))

    assert session.user_id == service.test_user_id
    assert session.requires_payment is False
    assert service._magic_link_key(token) not in redis.store

    with pytest.raises(InvalidMagicLinkToken):
        asyncio.run(service.verify_magic_link(token))


def test_magic_link_verify_rejects_expired_or_missing_token() -> None:
    service = FakeAuthService(MagicLinkRedis())

    with pytest.raises(InvalidMagicLinkToken):
        asyncio.run(service.verify_magic_link(uuid4()))


def test_magic_link_requires_payment_when_payload_marks_exhausted_guest() -> None:
    redis = MagicLinkRedis()
    service = FakeAuthService(redis)
    token = uuid4()
    redis.store[service._magic_link_key(token)] = service._encode_magic_link_payload(
        MagicLinkPayload(email="person@example.com", requires_payment=True)
    )

    session = asyncio.run(service.verify_magic_link(token))

    assert session.requires_payment is True


def test_mercadopago_webhook_signature_uses_manifest_headers() -> None:
    service = PaymentService(
        db_session=object(),  # type: ignore[arg-type]
        redis_client=object(),  # type: ignore[arg-type]
        settings=Settings(mercadopago_webhook_secret="webhook-secret"),
    )
    data_id = "123456"
    request_id = "bb56a2f1-6aae-46ac-982e-9dcd3581d08e"
    timestamp = "1742505638683"
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(b"webhook-secret", manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    signature = f"ts={timestamp},v1={digest}"

    assert service.validate_webhook_signature(signature, request_id, data_id)
    assert not service.validate_webhook_signature(signature, "other-request", data_id)
    assert not service.validate_webhook_signature("invalid", request_id, data_id)
    assert not service.validate_webhook_signature(signature, request_id, None)


def test_mercadopago_charge_response_extracts_pix_qr_code() -> None:
    service = PaymentService(
        db_session=object(),  # type: ignore[arg-type]
        redis_client=object(),  # type: ignore[arg-type]
        settings=Settings(analysis_price_cents=1990),
    )
    response = httpx.Response(
        201,
        json={
            "id": 123456,
            "date_of_expiration": "2026-05-03T15:30:00Z",
            "point_of_interaction": {
                "transaction_data": {
                    "qr_code": "000201PIX",
                    "qr_code_base64": "iVBORw0KGgoAAAANSUhEUgAAA",
                }
            },
        },
    )

    charge = service._parse_charge_response(response)

    assert isinstance(charge, PaymentCharge)
    assert charge.billing_id == "123456"
    assert charge.pix_copy_paste == "000201PIX"
    assert charge.pix_qr_code == "iVBORw0KGgoAAAANSUhEUgAAA"
    assert charge.amount_cents == 1990


def test_mercadopago_expiration_uses_required_date_format() -> None:
    expires_at = datetime(2026, 5, 3, 15, 30, 0, tzinfo=UTC)

    formatted = PaymentService._format_mercadopago_datetime(expires_at)

    assert formatted == "2026-05-03T15:30:00.000+00:00"


def test_mercadopago_webhook_url_skips_local_development_urls() -> None:
    service = PaymentService(
        db_session=object(),  # type: ignore[arg-type]
        redis_client=object(),  # type: ignore[arg-type]
        settings=Settings(api_public_url="http://localhost:3001"),
    )

    assert service._mercadopago_webhook_url() is None


def test_mercadopago_webhook_url_uses_public_https_url() -> None:
    service = PaymentService(
        db_session=object(),  # type: ignore[arg-type]
        redis_client=object(),  # type: ignore[arg-type]
        settings=Settings(api_public_url="https://api.parserly.com.br/"),
    )

    assert service._mercadopago_webhook_url() == (
        "https://api.parserly.com.br/api/v1/payments/webhook"
    )


class RecordingPaymentService(PaymentService):
    def __init__(self, status: str, payment_payload: dict[str, object] | None = None) -> None:
        self.calls: list[tuple[str, str, UUID | None]] = []
        self.status = status
        self.payment_payload = payment_payload
        super().__init__(
            db_session=object(),  # type: ignore[arg-type]
            redis_client=object(),  # type: ignore[arg-type]
            settings=Settings(),
        )

    async def _fetch_mercadopago_payment(self, payment_id: str) -> dict[str, object] | None:
        return self.payment_payload or {"id": payment_id, "status": "approved", "metadata": {}}

    async def _process_paid_event(
        self,
        billing_id: str,
        payload_user_id: UUID | None,
    ) -> WebhookProcessResult:
        self.calls.append(("paid", billing_id, payload_user_id))
        return WebhookProcessResult(status=self.status, billing_id=billing_id)

    async def _process_expired_event(self, billing_id: str) -> WebhookProcessResult:
        self.calls.append(("expired", billing_id, None))
        return WebhookProcessResult(status=self.status, billing_id=billing_id)


def test_payment_webhook_routes_paid_duplicate_event_idempotently() -> None:
    user_id = uuid4()
    service = RecordingPaymentService(
        status="duplicate",
        payment_payload={
            "id": "123456",
            "status": "approved",
            "metadata": {"user_id": str(user_id)},
        },
    )
    payload = {
        "action": "payment.updated",
        "type": "payment",
        "data": {
            "id": "123456",
        },
    }

    result = asyncio.run(service.process_webhook(json.dumps(payload).encode("utf-8")))

    assert result.status == "duplicate"
    assert service.calls == [("paid", "123456", user_id)]


def test_payment_webhook_routes_expired_event() -> None:
    service = RecordingPaymentService(
        status="expired",
        payment_payload={"id": "123456", "status": "cancelled", "metadata": {}},
    )
    payload = {"action": "payment.updated", "type": "payment", "data": {"id": "123456"}}

    result = asyncio.run(service.process_webhook(json.dumps(payload).encode("utf-8")))

    assert result.status == "expired"
    assert service.calls == [("expired", "123456", None)]


def test_payment_webhook_rejects_invalid_payload_and_ignores_missing_payment_id() -> None:
    service = RecordingPaymentService(status="processed")

    with pytest.raises(InvalidWebhookPayload):
        asyncio.run(service.process_webhook(b"{not-json"))

    result = asyncio.run(service.process_webhook(b'{"action":"payment.updated","data":{}}'))

    assert result.status == "ignored"
    assert service.calls == []
