from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.observability import log_structured
from app.models.payment import Payment
from app.models.user import User

logger = logging.getLogger(__name__)

MERCADOPAGO_PIX_EXPIRATION_SECONDS = 35 * 60
PAID_ANALYSIS_CREDITS = 10
CREATE_CHARGE_RATE_LIMIT_SECONDS = 60 * 60
CREATE_CHARGE_RATE_LIMIT_MAX_REQUESTS = 5
MERCADOPAGO_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
MERCADOPAGO_MAX_ATTEMPTS = 3
MERCADOPAGO_RETRY_DELAY_SECONDS = 0.75
MERCADOPAGO_RETRY_STATUS_CODES = {500, 502, 503, 504}
MERCADOPAGO_FINAL_UNPAID_STATUSES = {
    "cancelled",
    "canceled",
    "charged_back",
    "expired",
    "refunded",
    "rejected",
}

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
            provider_charge = (
                self._create_mock_pix(user)
                if self.settings.mercadopago_mock_payments
                else await self._create_mercadopago_pix(user)
            )
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
            log_structured(
                logger,
                logging.WARNING,
                "mercadopago_duplicate_payment_id",
                billing_id=provider_charge.billing_id,
            )
            raise PaymentProviderUnavailable from exc
        except Exception:
            await self.db_session.rollback()
            raise

        return provider_charge

    def _create_mock_pix(self, user: User) -> PaymentCharge:
        expires_at = datetime.now(UTC) + timedelta(seconds=MERCADOPAGO_PIX_EXPIRATION_SECONDS)
        billing_id = f"mock-{uuid4()}"
        pix_copy_paste = "|".join(
            (
                "PARSERLY_MOCK_PIX",
                "NAO_PAGUE",
                f"billing_id={billing_id}",
                f"amount_cents={self.settings.analysis_price_cents}",
            )
        )

        return PaymentCharge(
            billing_id=billing_id,
            pix_qr_code="",
            pix_copy_paste=pix_copy_paste,
            expires_at=expires_at,
            expires_in=MERCADOPAGO_PIX_EXPIRATION_SECONDS,
            amount_cents=self.settings.analysis_price_cents,
            analysis_credits=PAID_ANALYSIS_CREDITS,
        )

    def validate_webhook_signature(
        self,
        signature: str | None,
        request_id: str | None,
        data_id: str | None,
    ) -> bool:
        secret = self.settings.mercadopago_webhook_secret
        if not secret or not signature or not request_id or not data_id:
            return False

        signature_parts = self._parse_mercadopago_signature(signature)
        timestamp = signature_parts.get("ts")
        received_hash = signature_parts.get("v1")
        if not timestamp or not received_hash:
            return False

        manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
        expected = hmac.new(
            secret.encode("utf-8"),
            manifest.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, received_hash)

    async def process_webhook(
        self,
        payload: bytes,
        *,
        data_id: str | None = None,
    ) -> WebhookProcessResult:
        try:
            event_payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise InvalidWebhookPayload from exc

        if not isinstance(event_payload, dict):
            raise InvalidWebhookPayload

        payment_id = self._extract_payment_id(event_payload, data_id)
        if payment_id is None:
            log_structured(logger, logging.WARNING, "mercadopago_webhook_missing_payment_id")
            return WebhookProcessResult(status="ignored")

        event_type = self._extract_event_type(event_payload)
        if not self._is_mercadopago_payment_event(event_payload, event_type):
            log_structured(
                logger,
                logging.INFO,
                "mercadopago_webhook_ignored_event",
                event_type=event_type,
                billing_id=payment_id,
            )
            return WebhookProcessResult(status="ignored", billing_id=payment_id)

        payment_payload = await self._fetch_mercadopago_payment(payment_id)
        if payment_payload is None:
            return WebhookProcessResult(status="ignored", billing_id=payment_id)

        payment_status = self._extract_payment_status(payment_payload)
        if payment_status == "approved":
            user_id = self._extract_user_id(payment_payload)
            return await self._process_paid_event(payment_id, user_id)

        if payment_status in MERCADOPAGO_FINAL_UNPAID_STATUSES:
            return await self._process_expired_event(payment_id)

        log_structured(
            logger,
            logging.INFO,
            "mercadopago_webhook_ignored_payment_status",
            event_type=event_type,
            billing_id=payment_id,
            payment_status=payment_status,
        )
        return WebhookProcessResult(status="ignored", billing_id=payment_id)

    async def _create_mercadopago_pix(self, user: User) -> PaymentCharge:
        access_token = self._mercadopago_access_token()

        if self._uses_unsupported_test_access_token(access_token):
            raise PaymentProviderUnavailable(
                "O token TEST do Mercado Pago nao gera PIX neste fluxo. "
                "Use credenciais de producao de uma conta vendedor de teste "
                "ou credenciais de producao ativadas."
            )

        expires_at = datetime.now(UTC) + timedelta(seconds=MERCADOPAGO_PIX_EXPIRATION_SECONDS)
        idempotency_key = f"parserly-{uuid4()}"
        payload = {
            "transaction_amount": self._analysis_price_reais(),
            "description": f"Pacote Parserly - {PAID_ANALYSIS_CREDITS} analises ATS",
            "payment_method_id": "pix",
            "payer": {
                "email": user.email,
            },
            "external_reference": idempotency_key,
            "date_of_expiration": self._format_mercadopago_datetime(expires_at),
            "metadata": {
                "user_id": str(user.id),
                "analysis_credits": PAID_ANALYSIS_CREDITS,
            },
        }
        notification_url = self._mercadopago_webhook_url()
        if notification_url is not None:
            payload["notification_url"] = notification_url

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=MERCADOPAGO_TIMEOUT) as client:
            for attempt in range(1, MERCADOPAGO_MAX_ATTEMPTS + 1):
                started_at = monotonic()
                try:
                    response = await client.post(
                        self._mercadopago_url("/v1/payments"),
                        headers=self._mercadopago_headers(idempotency_key=idempotency_key),
                        json=payload,
                    )
                    if response.status_code in MERCADOPAGO_RETRY_STATUS_CODES:
                        raise httpx.HTTPStatusError(
                            "Mercado Pago returned retryable status",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()
                    return self._parse_charge_response(response, expires_at)
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    self._log_mercadopago_request_error(
                        "create_charge",
                        exc,
                        attempt=attempt,
                        duration_ms=round((monotonic() - started_at) * 1000, 2),
                    )

                    if not self._should_retry_mercadopago_error(exc):
                        break

                if attempt < MERCADOPAGO_MAX_ATTEMPTS:
                    await asyncio.sleep(MERCADOPAGO_RETRY_DELAY_SECONDS)

        raise PaymentProviderUnavailable(self._mercadopago_user_message(last_error)) from last_error

    def _parse_charge_response(
        self,
        response: httpx.Response,
        expires_at_fallback: datetime | None = None,
    ) -> PaymentCharge:
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise PaymentProviderUnavailable from exc

        if not isinstance(payload, dict):
            raise PaymentProviderUnavailable

        billing_id = self._first_value(payload, ("id",))
        transaction_data = self._first_value(payload, ("point_of_interaction", "transaction_data"))
        if not isinstance(transaction_data, dict):
            transaction_data = {}

        pix_copy_paste = self._first_value(transaction_data, ("qr_code",))
        pix_qr_code = self._first_value(transaction_data, ("qr_code_base64",))
        expires_at_raw = self._first_value(payload, ("date_of_expiration",))

        if not billing_id or not pix_copy_paste or not pix_qr_code:
            log_structured(
                logger,
                logging.WARNING,
                "mercadopago_charge_response_invalid",
                has_billing_id=bool(billing_id),
                has_pix_copy_paste=bool(pix_copy_paste),
                has_pix_qr_code=bool(pix_qr_code),
                response=self._mercadopago_response_summary(response),
            )
            raise PaymentProviderUnavailable

        expires_at = self._parse_expires_at(expires_at_raw, expires_at_fallback)
        return PaymentCharge(
            billing_id=str(billing_id),
            pix_qr_code=str(pix_qr_code),
            pix_copy_paste=str(pix_copy_paste),
            expires_at=expires_at,
            expires_in=MERCADOPAGO_PIX_EXPIRATION_SECONDS,
            amount_cents=self.settings.analysis_price_cents,
            analysis_credits=PAID_ANALYSIS_CREDITS,
        )

    async def _fetch_mercadopago_payment(self, payment_id: str) -> dict[str, Any] | None:
        self._mercadopago_access_token()

        async with httpx.AsyncClient(timeout=MERCADOPAGO_TIMEOUT) as client:
            try:
                response = await client.get(
                    self._mercadopago_url(f"/v1/payments/{payment_id}"),
                    headers=self._mercadopago_headers(),
                )
                if response.status_code == 404:
                    log_structured(
                        logger,
                        logging.WARNING,
                        "mercadopago_payment_not_found",
                        billing_id=payment_id,
                    )
                    return None
                response.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                self._log_mercadopago_request_error("fetch_payment", exc)
                raise PaymentProviderUnavailable from exc

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise PaymentProviderUnavailable from exc

        if not isinstance(payload, dict):
            raise PaymentProviderUnavailable

        return payload

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
                log_structured(
                    logger,
                    logging.WARNING,
                    "mercadopago_webhook_duplicate",
                    billing_id=billing_id,
                    status="paid",
                )
                await self.db_session.rollback()
                return WebhookProcessResult(status="duplicate", billing_id=billing_id)

            log_structured(
                logger,
                logging.WARNING,
                "mercadopago_webhook_unknown_payment_id",
                billing_id=billing_id,
                event_status="paid",
            )
            await self.db_session.rollback()
            return WebhookProcessResult(status="ignored", billing_id=billing_id)

        if payload_user_id is not None and payload_user_id != payment_user_id:
            log_structured(
                logger,
                logging.WARNING,
                "mercadopago_webhook_user_mismatch",
                billing_id=billing_id,
            )

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
        update_result = await self.db_session.execute(
            update(Payment)
            .where(Payment.billing_id == billing_id, Payment.status == "pending")
            .values(status="expired")
            .returning(Payment.id)
        )
        expired_payment_id = update_result.scalar_one_or_none()
        if expired_payment_id is None:
            existing_payment = await self._get_payment_by_billing_id(billing_id)
            if existing_payment is not None and existing_payment.status in {"expired", "paid"}:
                await self.db_session.rollback()
                return WebhookProcessResult(status="duplicate", billing_id=billing_id)

            await self.db_session.rollback()
            return WebhookProcessResult(status="ignored", billing_id=billing_id)

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
            log_structured(
                logger,
                logging.ERROR,
                "payment_unlock_publish_failed",
                user_id=str(user_id),
            )

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
            log_structured(
                logger,
                logging.ERROR,
                "payment_rate_limit_release_failed",
                user_id=str(user_id),
            )

    async def _get_payment_by_billing_id(self, billing_id: str) -> Payment | None:
        result = await self.db_session.execute(
            select(Payment).where(Payment.billing_id == billing_id)
        )
        return result.scalar_one_or_none()

    def _mercadopago_url(self, path: str) -> str:
        base_url = self.settings.mercadopago_api_url.strip()
        if not base_url:
            raise PaymentProviderUnavailable("A URL da API do Mercado Pago nao esta configurada.")
        if "\r" in base_url or "\n" in base_url:
            raise PaymentProviderUnavailable("A URL da API do Mercado Pago esta mal formatada.")

        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    def _mercadopago_headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._mercadopago_access_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        return headers

    def _mercadopago_access_token(self) -> str:
        access_token = self.settings.mercadopago_access_token.strip()
        if not access_token:
            raise PaymentProviderUnavailable("O access token do Mercado Pago nao esta configurado.")
        if "\r" in access_token or "\n" in access_token:
            raise PaymentProviderUnavailable(
                "O access token do Mercado Pago esta mal formatado. "
                "Remova quebras de linha da variavel MERCADOPAGO_ACCESS_TOKEN."
            )

        return access_token

    def _uses_unsupported_test_access_token(self, access_token: str | None = None) -> bool:
        token = access_token if access_token is not None else self._mercadopago_access_token()
        return token.upper().startswith("TEST-")

    def _mercadopago_webhook_url(self) -> str | None:
        notification_url = f"{self.settings.api_public_url.rstrip('/')}/api/v1/payments/webhook"
        if not self._is_valid_mercadopago_notification_url(notification_url):
            return None

        return notification_url

    @staticmethod
    def _is_valid_mercadopago_notification_url(value: str) -> bool:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or not parsed.hostname:
            return False

        hostname = parsed.hostname.lower()
        if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
            return False

        try:
            host_ip = ipaddress.ip_address(hostname)
        except ValueError:
            return True

        return not (
            host_ip.is_loopback
            or host_ip.is_private
            or host_ip.is_link_local
            or host_ip.is_reserved
            or host_ip.is_unspecified
        )

    def _analysis_price_reais(self) -> float:
        return round(self.settings.analysis_price_cents / 100, 2)

    @staticmethod
    def _parse_mercadopago_signature(signature: str) -> dict[str, str]:
        parts: dict[str, str] = {}
        for raw_part in signature.split(","):
            key_value = raw_part.split("=", 1)
            if len(key_value) != 2:
                continue
            key, value = key_value
            parts[key.strip()] = value.strip()
        return parts

    @staticmethod
    def _is_mercadopago_payment_event(
        payload: dict[str, Any],
        event_type: str | None,
    ) -> bool:
        candidates = [
            event_type,
            PaymentService._first_value(payload, ("type",)),
            PaymentService._first_value(payload, ("topic",)),
            PaymentService._first_value(payload, ("event",)),
        ]
        for candidate in candidates:
            if candidate is None:
                continue
            normalized_event_type = str(candidate).lower()
            if normalized_event_type == "payment" or normalized_event_type.startswith("payment."):
                return True
        return False

    @staticmethod
    def _should_retry_mercadopago_error(exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            return exc.response.status_code in MERCADOPAGO_RETRY_STATUS_CODES

        return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))

    @staticmethod
    def _log_mercadopago_request_error(
        action: str,
        exc: Exception,
        *,
        attempt: int | None = None,
        duration_ms: float | None = None,
    ) -> None:
        extra: dict[str, object] = {}
        if attempt is not None:
            extra["attempt"] = attempt
        if duration_ms is not None:
            extra["duration_ms"] = duration_ms

        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            log_structured(
                logger,
                logging.WARNING,
                "mercadopago_request_failed",
                action=action,
                status=exc.response.status_code,
                response=PaymentService._mercadopago_response_summary(exc.response),
                **extra,
            )
            return

        log_structured(
            logger,
            logging.WARNING,
            "mercadopago_request_failed",
            action=action,
            error=exc.__class__.__name__,
            **extra,
        )

    @staticmethod
    def _mercadopago_user_message(exc: Exception | None) -> str:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            if exc.response.status_code in {401, 403}:
                return "O access token do Mercado Pago e invalido ou nao tem permissao."

            if exc.response.status_code in MERCADOPAGO_RETRY_STATUS_CODES:
                return "Mercado Pago retornou erro temporario ao gerar a cobranca PIX. Tente novamente em instantes."

            provider_error = PaymentService._mercadopago_error_value(exc.response)
            if PaymentService._is_mercadopago_pix_key_missing_error(exc.response):
                return (
                    "O PIX do Mercado Pago nao esta habilitado para a conta recebedora. "
                    "Cadastre e ative uma chave Pix nessa conta ou use o access token "
                    "de uma conta vendedora com Pix habilitado."
                )
            if provider_error:
                return f"Mercado Pago recusou a cobranca PIX: {provider_error}"

        return "Nao foi possivel gerar a cobranca PIX no momento."

    @staticmethod
    def _mercadopago_error_value(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message

        error = payload.get("error")
        if isinstance(error, str) and error.strip():
            return error

        cause = payload.get("cause")
        if isinstance(cause, list):
            for item in cause:
                if isinstance(item, dict) and isinstance(item.get("description"), str):
                    return item["description"]

        return None

    @staticmethod
    def _is_mercadopago_pix_key_missing_error(response: httpx.Response) -> bool:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return False

        if not isinstance(payload, dict):
            return False

        message = payload.get("message")
        if (
            isinstance(message, str)
            and "collector user without key enabled for qr render" in message.lower()
        ):
            return True

        cause = payload.get("cause")
        if not isinstance(cause, list):
            return False

        for item in cause:
            if not isinstance(item, dict):
                continue

            if item.get("code") == 13253:
                return True

            description = item.get("description")
            if (
                isinstance(description, str)
                and "collector user without key enabled for qr render" in description.lower()
            ):
                return True

        return False

    @staticmethod
    def _mercadopago_response_summary(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return response.text[:240]

        if not isinstance(payload, dict):
            return str(payload)[:240]

        summary: dict[str, Any] = {}
        for key in ("error", "message", "status", "status_detail"):
            if key in payload:
                summary[key] = payload[key]

        cause = payload.get("cause")
        if isinstance(cause, list):
            summary["cause_count"] = len(cause)
            first_cause = cause[0] if cause else None
            if isinstance(first_cause, dict):
                for key in ("code", "description"):
                    if key in first_cause:
                        summary[f"cause.0.{key}"] = first_cause[key]

        return json.dumps(summary or payload, ensure_ascii=True)[:500]

    @staticmethod
    def _extract_event_type(payload: dict[str, Any]) -> str | None:
        value = PaymentService._first_value(
            payload,
            ("action",),
            ("type",),
            ("topic",),
            ("event",),
            ("event_type",),
            ("data", "event"),
        )
        return str(value) if value is not None else None

    @staticmethod
    def _extract_payment_id(
        payload: dict[str, Any],
        fallback_payment_id: str | None,
    ) -> str | None:
        if fallback_payment_id:
            return str(fallback_payment_id)

        value = PaymentService._first_value(
            payload,
            ("data", "id"),
            ("payment", "id"),
            ("resource",),
        )
        if value is None:
            return None

        payment_id = str(value)
        if "/" in payment_id:
            payment_id = payment_id.rstrip("/").rsplit("/", 1)[-1]

        return payment_id or None

    @staticmethod
    def _extract_payment_status(payload: dict[str, Any]) -> str | None:
        value = PaymentService._first_value(payload, ("status",))
        return str(value).lower() if value is not None else None

    @staticmethod
    def _extract_user_id(payload: dict[str, Any]) -> UUID | None:
        metadata = PaymentService._first_value(payload, ("metadata",))
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
    def _parse_expires_at(
        value: Any,
        fallback: datetime | None = None,
    ) -> datetime:
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                parsed = None
            if parsed is not None:
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=UTC)
                return parsed

        if fallback is not None:
            return fallback

        return datetime.now(UTC) + timedelta(seconds=MERCADOPAGO_PIX_EXPIRATION_SECONDS)

    @staticmethod
    def _format_mercadopago_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)

        return value.isoformat(timespec="milliseconds")

    @staticmethod
    def _create_charge_rate_limit_key(user_id: UUID) -> str:
        return f"payments:create-charge:rate:{user_id}"
