from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.payment import Payment
from app.models.user import User

logger = logging.getLogger(__name__)

ABACATEPAY_PIX_EXPIRATION_SECONDS = 30 * 60
PAID_ANALYSIS_CREDITS = 10
CREATE_CHARGE_RATE_LIMIT_SECONDS = 60 * 60
CREATE_CHARGE_RATE_LIMIT_MAX_REQUESTS = 5
ABACATEPAY_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)

_RATE_LIMIT_SCRIPT = """
local current = tonumber(redis.call("GET", KEYS[1]) or "0")
local limit = tonumber(ARGV[2])
if current >= limit then
    local ttl = redis.call("TTL", KEYS[1])
    if ttl < 0 then
        redis.call("EXPIRE", KEYS[1], ARGV[1])
        ttl = tonumber(ARGV[1])
    end
    return { current, ttl, 0 }
end

current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
local ttl = redis.call("TTL", KEYS[1])
return { current, ttl, 1 }
"""

_RELEASE_RATE_LIMIT_SCRIPT = """
local current = redis.call("DECR", KEYS[1])
if current <= 0 then
    redis.call("DEL", KEYS[1])
    return 0
end
return current
"""


class PaymentRateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("payment create-charge rate limit exceeded")


class PaymentProviderUnavailable(Exception):
    def __init__(self, message: str | None = None) -> None:
        self.message = message or "Nao foi possivel gerar a cobranca PIX no momento."
        super().__init__(self.message)


class InvalidWebhookPayload(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PaymentCharge:
    billing_id: str
    pix_qr_code: str
    pix_copy_paste: str
    expires_at: datetime
    expires_in: int
    amount_cents: int
    analysis_credits: int


@dataclass(frozen=True, slots=True)
class WebhookProcessResult:
    status: str
    billing_id: str | None = None


class PaymentService:
    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        settings: Settings,
    ) -> None:
        self.db_session = db_session
        self.redis = redis_client
        self.settings = settings

    async def create_charge(self, user: User) -> PaymentCharge:
        await self._enforce_create_charge_rate_limit(user.id)

        try:
            provider_charge = await self._create_abacatepay_pix(user)
        except PaymentProviderUnavailable:
            await self._release_create_charge_rate_limit(user.id)
            raise

        payment = Payment(
            user_id=user.id,
            billing_id=provider_charge.billing_id,
            amount_cents=provider_charge.amount_cents,
            status="pending",
        )
        self.db_session.add(payment)

        try:
            await self.db_session.commit()
        except IntegrityError as exc:
            await self.db_session.rollback()
            logger.warning(
                "Duplicate billing_id returned by AbacatePay: %s",
                provider_charge.billing_id,
            )
            raise PaymentProviderUnavailable from exc
        except Exception:
            await self.db_session.rollback()
            raise

        return provider_charge

    def validate_webhook_signature(self, payload: bytes, signature: str | None) -> bool:
        secret = self.settings.abacatepay_webhook_secret
        if not secret or not signature:
            return False

        expected = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        received = signature.strip()
        received_without_prefix = received.removeprefix("sha256=").strip()

        return hmac.compare_digest(expected, received_without_prefix) or hmac.compare_digest(
            f"sha256={expected}",
            received,
        )

    async def process_webhook(self, payload: bytes) -> WebhookProcessResult:
        try:
            event_payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise InvalidWebhookPayload from exc

        if not isinstance(event_payload, dict):
            raise InvalidWebhookPayload

        event_type = self._extract_event_type(event_payload)
        billing_id = self._extract_billing_id(event_payload)
        if billing_id is None:
            logger.warning("AbacatePay webhook without billing_id")
            return WebhookProcessResult(status="ignored")

        if event_type in {"billing.paid", "transparent.completed", "checkout.completed"}:
            user_id = self._extract_user_id(event_payload)
            return await self._process_paid_event(billing_id, user_id)

        if event_type in {"billing.expired", "transparent.lost", "checkout.lost"}:
            return await self._process_expired_event(billing_id)

        logger.info("Ignored AbacatePay webhook event type: %s", event_type)
        return WebhookProcessResult(status="ignored", billing_id=billing_id)

    async def _create_abacatepay_pix(self, user: User) -> PaymentCharge:
        if not self.settings.abacatepay_api_key:
            raise PaymentProviderUnavailable("A chave da AbacatePay nao esta configurada.")

        payload = {
            "method": "PIX",
            "data": {
                "amount": self.settings.analysis_price_cents,
                "description": f"Pacote Parserly - {PAID_ANALYSIS_CREDITS} analises ATS",
                "expiresIn": ABACATEPAY_PIX_EXPIRATION_SECONDS,
            },
        }

        async with httpx.AsyncClient(timeout=ABACATEPAY_TIMEOUT) as client:
            try:
                response = await client.post(
                    self._abacatepay_url("/transparents/create"),
                    headers=self._abacatepay_headers(),
                    json=payload,
                )
                response.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                self._log_abacatepay_request_error(exc)
                raise PaymentProviderUnavailable(self._abacatepay_user_message(exc)) from exc

        return self._parse_charge_response(response)

    def _parse_charge_response(self, response: httpx.Response) -> PaymentCharge:
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise PaymentProviderUnavailable from exc

        if not isinstance(payload, dict):
            raise PaymentProviderUnavailable
        if payload.get("success") is False:
            raise PaymentProviderUnavailable

        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise PaymentProviderUnavailable

        billing_id = self._first_value(
            data,
            ("id",),
            ("billingId",),
            ("billing_id",),
            ("pixQrCode", "id"),
            ("pix", "id"),
        )
        pix_copy_paste = self._first_value(
            data,
            ("brCode",),
            ("pixCopyPaste",),
            ("pix_copy_paste",),
            ("copyPaste",),
            ("pix", "brCode"),
        )
        pix_qr_code = self._first_value(
            data,
            ("brCodeBase64",),
            ("pixQrCode",),
            ("pix_qr_code",),
            ("qrCode",),
            ("pix", "brCodeBase64"),
        )
        expires_at_raw = self._first_value(
            data,
            ("expiresAt",),
            ("expires_at",),
            ("expirationDate",),
            ("pix", "expiresAt"),
        )

        if not billing_id or not pix_copy_paste or not pix_qr_code:
            logger.warning(
                "AbacatePay create-charge response missing required fields: "
                "billing_id=%s pix_copy_paste=%s pix_qr_code=%s response=%s",
                bool(billing_id),
                bool(pix_copy_paste),
                bool(pix_qr_code),
                self._abacatepay_response_summary(response),
            )
            raise PaymentProviderUnavailable

        expires_at = self._parse_expires_at(expires_at_raw)
        return PaymentCharge(
            billing_id=str(billing_id),
            pix_qr_code=str(pix_qr_code),
            pix_copy_paste=str(pix_copy_paste),
            expires_at=expires_at,
            expires_in=ABACATEPAY_PIX_EXPIRATION_SECONDS,
            amount_cents=self.settings.analysis_price_cents,
            analysis_credits=PAID_ANALYSIS_CREDITS,
        )

    async def _process_paid_event(
        self,
        billing_id: str,
        payload_user_id: UUID | None,
    ) -> WebhookProcessResult:
        update_result = await self.db_session.execute(
            update(Payment)
            .where(Payment.billing_id == billing_id, Payment.status != "paid")
            .values(status="paid", confirmed_at=func.now())
            .returning(Payment.user_id)
        )
        payment_user_id = update_result.scalar_one_or_none()

        if payment_user_id is None:
            existing_payment = await self._get_payment_by_billing_id(billing_id)
            if existing_payment is not None and existing_payment.status == "paid":
                logger.warning("Duplicate webhook received for billing_id: %s", billing_id)
                await self.db_session.rollback()
                return WebhookProcessResult(status="duplicate", billing_id=billing_id)

            logger.warning("Paid webhook for unknown billing_id: %s", billing_id)
            await self.db_session.rollback()
            return WebhookProcessResult(status="ignored", billing_id=billing_id)

        if payload_user_id is not None and payload_user_id != payment_user_id:
            logger.warning("Webhook user_id metadata does not match billing_id: %s", billing_id)

        await self.db_session.execute(
            update(User)
            .where(User.id == payment_user_id)
            .values(
                analyses_used=User.analyses_used - PAID_ANALYSIS_CREDITS,
                updated_at=func.now(),
            )
        )

        try:
            await self.db_session.commit()
        except Exception:
            await self.db_session.rollback()
            raise

        await self._publish_analysis_unlocked(payment_user_id)
        return WebhookProcessResult(status="processed", billing_id=billing_id)

    async def _process_expired_event(self, billing_id: str) -> WebhookProcessResult:
        await self.db_session.execute(
            update(Payment)
            .where(Payment.billing_id == billing_id, Payment.status != "paid")
            .values(status="expired")
        )
        await self.db_session.commit()
        return WebhookProcessResult(status="expired", billing_id=billing_id)

    async def _publish_analysis_unlocked(self, user_id: UUID) -> None:
        channel = f"analysis_unlocked:{user_id}"
        message = json.dumps(
            {
                "event": "payment_confirmed",
                "user_id": str(user_id),
                "analysis_credits": PAID_ANALYSIS_CREDITS,
            }
        )
        try:
            await self.redis.publish(channel, message)
        except Exception:
            logger.exception("Failed to publish analysis unlock event for user_id: %s", user_id)

    async def _enforce_create_charge_rate_limit(self, user_id: UUID) -> None:
        result = await self.redis.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            self._create_charge_rate_limit_key(user_id),
            CREATE_CHARGE_RATE_LIMIT_SECONDS,
            CREATE_CHARGE_RATE_LIMIT_MAX_REQUESTS,
        )
        current_count, ttl, allowed = int(result[0]), int(result[1]), int(result[2])
        if not allowed:
            raise PaymentRateLimitExceeded(retry_after=max(ttl, 1))

    async def _release_create_charge_rate_limit(self, user_id: UUID) -> None:
        try:
            await self.redis.eval(
                _RELEASE_RATE_LIMIT_SCRIPT,
                1,
                self._create_charge_rate_limit_key(user_id),
            )
        except Exception:
            logger.exception("Failed to release create-charge rate limit for user_id: %s", user_id)

    async def _get_payment_by_billing_id(self, billing_id: str) -> Payment | None:
        result = await self.db_session.execute(
            select(Payment).where(Payment.billing_id == billing_id)
        )
        return result.scalar_one_or_none()

    def _abacatepay_url(self, path: str) -> str:
        return f"{self.settings.abacatepay_api_url.rstrip('/')}/{path.lstrip('/')}"

    def _abacatepay_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.abacatepay_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _log_abacatepay_request_error(exc: Exception) -> None:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            logger.warning(
                "AbacatePay create-charge request failed: status=%s response=%s",
                exc.response.status_code,
                PaymentService._abacatepay_response_summary(exc.response),
            )
            return

        logger.warning(
            "AbacatePay create-charge request failed: error=%s",
            exc.__class__.__name__,
        )

    @staticmethod
    def _abacatepay_user_message(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            provider_error = PaymentService._abacatepay_error_value(exc.response)
            if exc.response.status_code == 401 and provider_error == "Insufficient permissions":
                return (
                    "A chave da AbacatePay nao tem permissao para criar checkout "
                    "transparente PIX. Gere uma chave com permissao CHECKOUT:READ."
                )
            if exc.response.status_code == 401 and provider_error == "API key version mismatch":
                return "A chave da AbacatePay nao e compativel com esta versao da API."
            if exc.response.status_code == 401 and provider_error == "Invalid or inactive API key":
                return "A chave da AbacatePay e invalida ou esta inativa."

        return "Nao foi possivel gerar a cobranca PIX no momento."

    @staticmethod
    def _abacatepay_error_value(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        error = payload.get("error")
        return error if isinstance(error, str) else None

    @staticmethod
    def _abacatepay_response_summary(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return response.text[:240]

        if not isinstance(payload, dict):
            return str(payload)[:240]

        summary: dict[str, Any] = {}
        for key in ("success", "error", "message"):
            if key in payload:
                summary[key] = payload[key]

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("status", "message", "error"):
                if key in data:
                    summary[f"data.{key}"] = data[key]

        return json.dumps(summary or payload, ensure_ascii=True)[:500]

    @staticmethod
    def _extract_event_type(payload: dict[str, Any]) -> str | None:
        return PaymentService._first_value(
            payload,
            ("event",),
            ("event_type",),
            ("type",),
            ("name",),
            ("data", "event"),
        )

    @staticmethod
    def _extract_billing_id(payload: dict[str, Any]) -> str | None:
        value = PaymentService._first_value(
            payload,
            ("data", "id"),
            ("data", "billingId"),
            ("data", "billing_id"),
            ("data", "billing", "id"),
            ("data", "pix", "id"),
            ("billing", "id"),
            ("payment", "id"),
            ("pix", "id"),
            ("billing_id",),
            ("billingId",),
        )
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _extract_user_id(payload: dict[str, Any]) -> UUID | None:
        metadata = PaymentService._first_value(
            payload,
            ("data", "metadata"),
            ("data", "billing", "metadata"),
            ("data", "pix", "metadata"),
            ("billing", "metadata"),
            ("metadata",),
        )
        if not isinstance(metadata, dict):
            return None

        user_id = metadata.get("user_id")
        if user_id is None:
            return None

        try:
            return UUID(str(user_id))
        except ValueError:
            return None

    @staticmethod
    def _first_value(root: dict[str, Any], *paths: tuple[str, ...]) -> Any:
        for path in paths:
            current: Any = root
            for part in path:
                if not isinstance(current, dict) or part not in current:
                    current = None
                    break
                current = current[part]
            if current not in (None, ""):
                return current
        return None

    @staticmethod
    def _parse_expires_at(value: Any) -> datetime:
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                parsed = None
            if parsed is not None:
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=UTC)
                return parsed

        return datetime.now(UTC) + timedelta(seconds=ABACATEPAY_PIX_EXPIRATION_SECONDS)

    @staticmethod
    def _create_charge_rate_limit_key(user_id: UUID) -> str:
        return f"payments:create-charge:rate:{user_id}"
