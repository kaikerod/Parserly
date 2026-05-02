from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.core.quotas import FREE_ANALYSIS_LIMIT, guest_analysis_key
from app.api.v1.routers.analysis import GuestQuotaExceeded, release_reserved_guest_analysis
from app.api.v1.routers.analysis import reserve_guest_analysis
from app.services.auth_service import AuthService, InvalidMagicLinkToken, MagicLinkPayload
from app.services.payment_service import (
    InvalidWebhookPayload,
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


def test_webhook_signature_accepts_plain_and_prefixed_hmac() -> None:
    service = PaymentService(
        db_session=object(),  # type: ignore[arg-type]
        redis_client=object(),  # type: ignore[arg-type]
        settings=Settings(abacatepay_webhook_secret="webhook-secret"),
    )
    payload = b'{"event":"billing.paid","data":{"billingId":"bill_123"}}'
    digest = hmac.new(b"webhook-secret", payload, hashlib.sha256).hexdigest()

    assert service.validate_webhook_signature(payload, digest)
    assert service.validate_webhook_signature(payload, f"sha256={digest}")
    assert not service.validate_webhook_signature(payload, "invalid")
    assert not service.validate_webhook_signature(payload, None)


class RecordingPaymentService(PaymentService):
    def __init__(self, status: str) -> None:
        self.calls: list[tuple[str, str, UUID | None]] = []
        self.status = status
        super().__init__(
            db_session=object(),  # type: ignore[arg-type]
            redis_client=object(),  # type: ignore[arg-type]
            settings=Settings(),
        )

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
    service = RecordingPaymentService(status="duplicate")
    payload = {
        "event": "billing.paid",
        "data": {
            "billingId": "bill_123",
            "metadata": {"user_id": str(user_id)},
        },
    }

    result = asyncio.run(service.process_webhook(json.dumps(payload).encode("utf-8")))

    assert result.status == "duplicate"
    assert service.calls == [("paid", "bill_123", user_id)]


def test_payment_webhook_routes_expired_event() -> None:
    service = RecordingPaymentService(status="expired")
    payload = {"event": "billing.expired", "data": {"id": "bill_123"}}

    result = asyncio.run(service.process_webhook(json.dumps(payload).encode("utf-8")))

    assert result.status == "expired"
    assert service.calls == [("expired", "bill_123", None)]


def test_payment_webhook_rejects_invalid_payload_and_ignores_missing_billing_id() -> None:
    service = RecordingPaymentService(status="processed")

    with pytest.raises(InvalidWebhookPayload):
        asyncio.run(service.process_webhook(b"{not-json"))

    result = asyncio.run(service.process_webhook(b'{"event":"billing.paid","data":{}}'))

    assert result.status == "ignored"
    assert service.calls == []
