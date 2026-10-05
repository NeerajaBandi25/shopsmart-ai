"""Provider boundary and Stripe-hosted Checkout test-mode adapter."""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx

from src.core.config import settings
from src.core.exceptions import AppException
from src.core.payment_limits import (
    HOSTED_CHECKOUT_MAX_AMOUNT_CENTS,
    HOSTED_CHECKOUT_MIN_AMOUNT_CENTS,
    HOSTED_CHECKOUT_SESSION_TTL_SECONDS,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckoutSession:
    session_id: str
    checkout_url: str


@dataclass(frozen=True)
class VerifiedPaymentEvent:
    event_id: str
    event_type: str
    session_id: str
    order_id: str
    payment_id: str | None
    amount_cents: int
    currency: str
    status: str


class PaymentProvider(Protocol):
    """Payment interface consumed by order/payment application services."""

    name: str

    def is_configured(self) -> bool:
        ...

    def validate_checkout_configuration(self) -> None:
        """Fail before inventory reservation when static checkout configuration is invalid."""
        ...

    async def create_checkout_session(
        self,
        *,
        order_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        idempotency_key: str,
    ) -> CheckoutSession:
        ...

    async def retrieve_payment_state(self, session_id: str) -> VerifiedPaymentEvent | None:
        ...

    def verify_webhook(self, raw_body: bytes, signature: str | None) -> VerifiedPaymentEvent | None:
        ...

    async def refund(self, payment_id: str, amount_cents: int | None, idempotency_key: str) -> None:
        ...


def normalize_stripe_status(event_type: str, payment_status: str | None) -> str | None:
    """Map the small supported Stripe event set into domain states."""
    if event_type == "checkout.session.completed" and payment_status == "paid":
        return "succeeded"
    if event_type == "checkout.session.async_payment_failed":
        return "failed"
    if event_type == "checkout.session.expired":
        return "cancelled"
    return None


def _return_url(base_url: str, order_id: str, *, success: bool) -> str:
    """Add an owner-pollable order reference without trusting return query state."""
    parts = urlsplit(base_url)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.netloc
        or parts.username is not None
        or parts.password is not None
        or not parts.hostname
    ):
        raise AppException("Sandbox payment return URL is invalid", 503, "payment_config_invalid")
    hostname = parts.hostname.lower()
    local_origin = hostname in {"localhost", "127.0.0.1", "::1"}
    local_http_allowed = settings.app_env.strip().lower() in {"local", "dev", "development", "test"}
    origin = f"{parts.scheme}://{parts.netloc}"
    allowed_origins = {
        value.rstrip("/").lower() for value in settings.cors_origins if isinstance(value, str)
    }
    if parts.scheme != "https" and not (local_origin and local_http_allowed):
        raise AppException(
            "Sandbox payment return URL must use HTTPS", 503, "payment_config_invalid"
        )
    if parts.scheme == "https" and origin.lower() not in allowed_origins:
        raise AppException(
            "Sandbox payment return URL is not allowed", 503, "payment_config_invalid"
        )
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query)
        if key not in {"order_id", "session_id"}
    ]
    query.append(("order_id", order_id))
    if success:
        query.append(("session_id", "{CHECKOUT_SESSION_ID}"))
    encoded_query = urlencode(query).replace("%7BCHECKOUT_SESSION_ID%7D", "{CHECKOUT_SESSION_ID}")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, encoded_query, parts.fragment))


class StripePaymentProvider:
    """Stripe hosted checkout restricted to API credentials in test mode."""

    name = "stripe"
    endpoint = "https://api.stripe.com/v1"

    def __init__(self, secret_key: str | None = None, webhook_secret: str | None = None):
        self._secret_key = secret_key if secret_key is not None else settings.stripe_secret_key
        self._webhook_secret = (
            webhook_secret if webhook_secret is not None else settings.stripe_webhook_secret
        )

    def is_configured(self) -> bool:
        return bool(
            settings.payment_provider.strip().lower() == "stripe"
            and settings.payment_mode.strip().lower() == "test"
            and self._secret_key
            and self._secret_key.startswith("sk_test_")
            and self._webhook_secret
            and self._webhook_secret.startswith("whsec_")
        )

    def _require_test_credentials(self) -> None:
        if not self.is_configured():
            raise AppException(
                "Sandbox payments are not configured", 503, "payment_provider_unavailable"
            )

    def validate_checkout_configuration(self) -> None:
        """Validate credentials and return URLs before creating a local reservation."""
        self._require_test_credentials()
        _return_url(settings.payment_success_url, "preflight-order", success=True)
        _return_url(settings.payment_cancel_url, "preflight-order", success=False)

    async def create_checkout_session(
        self,
        *,
        order_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        idempotency_key: str,
    ) -> CheckoutSession:
        self._require_test_credentials()
        if (
            amount_cents < HOSTED_CHECKOUT_MIN_AMOUNT_CENTS
            or amount_cents > HOSTED_CHECKOUT_MAX_AMOUNT_CENTS
        ):
            raise AppException("Order amount is not supported", 422, "invalid_payment_amount")
        if currency.lower() != "inr":
            raise AppException("Only INR sandbox payments are supported", 422, "invalid_currency")
        success_url = _return_url(settings.payment_success_url, order_id, success=True)
        cancel_url = _return_url(settings.payment_cancel_url, order_id, success=False)
        form = {
            "mode": "payment",
            "payment_method_types[0]": "card",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "expires_at": str(int(time.time()) + HOSTED_CHECKOUT_SESSION_TTL_SECONDS),
            "client_reference_id": order_id,
            "metadata[order_id]": order_id,
            "line_items[0][price_data][currency]": "inr",
            "line_items[0][price_data][unit_amount]": str(amount_cents),
            "line_items[0][price_data][product_data][name]": "ShopSmart order",
            "line_items[0][price_data][product_data][description]": description[:300],
            "line_items[0][quantity]": "1",
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    f"{self.endpoint}/checkout/sessions",
                    data=form,
                    auth=(self._secret_key or "", ""),
                    headers={"Idempotency-Key": idempotency_key},
                )
            response.raise_for_status()
            payload = response.json()
            session_id, checkout_url = payload.get("id"), payload.get("url")
            if not isinstance(session_id, str) or not isinstance(checkout_url, str):
                raise ValueError("provider response missing session fields")
            return CheckoutSession(session_id=session_id, checkout_url=checkout_url)
        except httpx.HTTPStatusError as exc:
            # 409 can mean Stripe is still processing the same concurrent idempotent
            # request; 429 is also retryable. Neither proves there is no remote session.
            definitive_rejection = (
                400 <= exc.response.status_code < 500 and exc.response.status_code not in {409, 429}
            )
            error_code = (
                "payment_session_rejected" if definitive_rejection else "payment_session_failed"
            )
            logger.error(
                "payment_provider_operation_failed",
                extra={
                    "event": "PAYMENT_SESSION_FAILED",
                    "provider": self.name,
                    "operation": "create_checkout_session",
                    "error_code": error_code,
                    "provider_status_code": exc.response.status_code,
                },
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            raise AppException(
                "Payment provider rejected the checkout session. Review checkout and try again."
                if definitive_rejection
                else "Payment session could not be created. Retry checkout.",
                502,
                error_code,
            ) from exc
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            logger.error(
                "payment_provider_operation_failed",
                extra={
                    "event": "PAYMENT_SESSION_FAILED",
                    "provider": self.name,
                    "operation": "create_checkout_session",
                    "error_code": "provider_error",
                },
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            raise AppException(
                "Payment session could not be created. Retry checkout.",
                502,
                "payment_session_failed",
            ) from exc

    async def retrieve_payment_state(self, session_id: str) -> VerifiedPaymentEvent | None:
        """Retrieve and normalize the provider's session state without exposing payloads."""
        self._require_test_credentials()
        if not session_id.startswith("cs_"):
            raise AppException(
                "Payment session reference is invalid", 422, "invalid_payment_reference"
            )
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    f"{self.endpoint}/checkout/sessions/{quote(session_id, safe='')}",
                    auth=(self._secret_key or "", ""),
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            logger.error(
                "payment_provider_operation_failed",
                extra={
                    "event": "PAYMENT_RETRIEVE_FAILED",
                    "provider": self.name,
                    "operation": "retrieve_payment_state",
                    "error_code": "provider_error",
                },
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            raise AppException(
                "Payment state is temporarily unavailable", 502, "payment_retrieve_failed"
            ) from exc
        event_type = (
            "checkout.session.expired"
            if payload.get("status") == "expired"
            else "checkout.session.completed"
        )
        normalized = normalize_stripe_status(event_type, payload.get("payment_status"))
        if normalized is None:
            # An open, unpaid session remains payable; never release its reservation.
            if payload.get("status") == "open":
                return None
            raise AppException("Payment state is not available", 502, "payment_state_unknown")
        metadata = payload.get("metadata")
        metadata_order_id = metadata.get("order_id") if isinstance(metadata, dict) else None
        order_id = payload.get("client_reference_id") or metadata_order_id
        amount = payload.get("amount_total")
        currency = payload.get("currency")
        if (
            payload.get("id") != session_id
            or not isinstance(order_id, str)
            or not order_id
            or not isinstance(amount, int)
            or not isinstance(currency, str)
        ):
            raise AppException("Payment state is not available", 502, "payment_state_unknown")
        payment_intent = payload.get("payment_intent")
        return VerifiedPaymentEvent(
            event_id=f"reconcile:{session_id}:{normalized}",
            event_type=f"reconciliation.{normalized}",
            session_id=session_id,
            order_id=order_id,
            payment_id=payment_intent if isinstance(payment_intent, str) else None,
            amount_cents=amount,
            currency=currency.upper(),
            status=normalized,
        )

    def verify_webhook(self, raw_body: bytes, signature: str | None) -> VerifiedPaymentEvent | None:
        self._require_test_credentials()
        if not signature or len(raw_body) > 1_000_000:
            raise AppException("Invalid payment notification", 400, "invalid_webhook")
        parts = {}
        for entry in signature.split(","):
            key, separator, value = entry.partition("=")
            if separator:
                parts.setdefault(key, []).append(value)
        timestamps = parts.get("t", [])
        signatures = parts.get("v1", [])
        if not timestamps or not signatures or not timestamps[0].isdigit():
            raise AppException("Invalid payment notification", 400, "invalid_webhook")
        timestamp = int(timestamps[0])
        if abs(time.time() - timestamp) > 300:
            raise AppException("Expired payment notification", 400, "expired_webhook")
        signed = str(timestamp).encode() + b"." + raw_body
        digest = hmac.new((self._webhook_secret or "").encode(), signed, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(digest, item) for item in signatures):
            raise AppException("Invalid payment notification", 400, "invalid_webhook")
        try:
            body = json.loads(raw_body)
            event_id = body["id"]
            event_type = body["type"]
            if body.get("livemode") is not False:
                raise AppException(
                    "Live payment notifications are not accepted", 400, "live_webhook_rejected"
                )
            if not isinstance(event_id, str) or not isinstance(event_type, str):
                raise ValueError("invalid event envelope")
            if event_type not in {
                "checkout.session.completed",
                "checkout.session.async_payment_failed",
                "checkout.session.expired",
            }:
                return None
            obj = body["data"]["object"]
            session_id = obj["id"]
            order_id = obj.get("metadata", {}).get("order_id") or obj.get("client_reference_id")
            normalized = normalize_stripe_status(event_type, obj.get("payment_status"))
            if normalized is None:
                # Acknowledge signed but unpaid/unsupported states without domain authority.
                return None
            if (
                not all(
                    isinstance(value, str) and value
                    for value in (event_id, event_type, session_id, order_id)
                )
                or normalized is None
            ):
                raise ValueError("unsupported or incomplete event")
            amount = obj.get("amount_total")
            currency = obj.get("currency")
            if not isinstance(amount, int) or amount < 1 or not isinstance(currency, str):
                raise ValueError("invalid amount")
            payment_intent = obj.get("payment_intent")
            return VerifiedPaymentEvent(
                event_id=event_id,
                event_type=event_type,
                session_id=session_id,
                order_id=order_id,
                payment_id=payment_intent if isinstance(payment_intent, str) else None,
                amount_cents=amount,
                currency=currency.upper(),
                status=normalized,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AppException(
                "Unsupported payment notification", 400, "unsupported_webhook"
            ) from exc

    async def refund(self, payment_id: str, amount_cents: int | None, idempotency_key: str) -> None:
        self._require_test_credentials()
        if not payment_id.startswith("pi_"):
            raise AppException("Payment cannot be refunded", 422, "invalid_payment_reference")
        form: dict[str, Any] = {"payment_intent": payment_id}
        if amount_cents is not None:
            if amount_cents < 1:
                raise AppException("Refund amount is invalid", 422, "invalid_refund_amount")
            form["amount"] = str(amount_cents)
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    f"{self.endpoint}/refunds",
                    data=form,
                    auth=(self._secret_key or "", ""),
                    headers={"Idempotency-Key": idempotency_key},
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppException("Refund could not be processed", 502, "refund_failed") from exc


def get_payment_provider() -> PaymentProvider:
    """Application factory: never makes a provider/network call at startup."""
    return StripePaymentProvider()
