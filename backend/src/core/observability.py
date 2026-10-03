"""Lightweight request logging, request IDs, metrics, and security audit events."""

import hashlib
import hmac
import json
import logging
import re
import sys
import threading
import time
import traceback
from collections import Counter, defaultdict
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.config import settings

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)

_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_HTTP_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "TRACE", "CONNECT"}
)
_SECURITY_EVENTS = frozenset(
    {
        "registration_success",
        "registration_failure",
        "login_success",
        "login_failure",
        "login_rate_limited",
        "logout_success",
        "password_change_success",
        "password_change_failure",
        "authentication_failure",
        "authorization_denied",
    }
)
_AI_EVENTS = frozenset(
    {
        "ai_retrieval",
        "ai_no_answer",
        "ai_provider_failure",
        "ai_evaluation",
        "ai_provider_success",
        "ai_provider_fallback",
        "ai_policy_denied",
    }
)
_LOG_CONTEXT_FIELDS = frozenset(
    {
        "event",
        "success",
        "service",
        "tool",
        "method",
        "route",
        "intent",
        "operation",
        "promotion_id",
        "coupon_hash",
        "eligible",
        "discount_cents",
        "category",
        "min_price_cents",
        "max_price_cents",
        "in_stock_only",
        "result_count",
        "status_code",
        "duration_ms",
        "error_type",
        "error_code",
        "user_ref",
        "client_ref",
        "reason",
        "exception_type",
        "provider",
        "model",
        "data_classification",
        "fallback_used",
        "latency_ms",
        "routing_policy",
    }
)


class JsonLogFormatter(logging.Formatter):
    """Render log records as compact JSON with an allowlisted context."""

    def format(self, record: logging.LogRecord) -> str:
        context = {
            key: record.__dict__[key] for key in _LOG_CONTEXT_FIELDS if key in record.__dict__
        }
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": getattr(record, "request_id", None) or request_id_context.get(),
            "context": context,
        }
        if record.exc_info and record.exc_info[2]:
            payload["stack_trace"] = "".join(traceback.format_tb(record.exc_info[2]))
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_structured_logging(level: str = "INFO") -> None:
    """Ensure root logging uses one structured stream handler without duplicates."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler(sys.stdout))
    for handler in root_logger.handlers:
        handler.setFormatter(JsonLogFormatter())


class ApplicationMetrics:
    """Bounded, process-local counters and latency aggregates."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_counts: Counter[tuple[str, str]] = Counter()
        self._request_durations: dict[tuple[str, str], list[float]] = defaultdict(
            lambda: [0.0, 0.0, 0.0]
        )
        self._security_event_counts: Counter[str] = Counter()
        self._ai_event_counts: Counter[str] = Counter()

    def record_request(self, method: str, status_code: int, duration_ms: float) -> None:
        method_label = normalize_http_method(method)
        status_label = f"{status_code // 100}xx"
        key = (method_label, status_label)
        with self._lock:
            self._request_counts[key] += 1
            aggregate = self._request_durations[key]
            aggregate[0] += 1
            aggregate[1] += duration_ms
            aggregate[2] = max(aggregate[2], duration_ms)

    def record_security_event(self, event: str) -> None:
        if event not in _SECURITY_EVENTS:
            return
        with self._lock:
            self._security_event_counts[event] += 1

    def record_ai_event(self, event: str) -> None:
        if event not in _AI_EVENTS:
            return
        with self._lock:
            self._ai_event_counts[event] += 1

    def snapshot(self) -> dict[str, dict]:
        """Return a copy of metrics, with only bounded method/status/event keys."""
        with self._lock:
            return {
                "requests": {
                    f"{method}:{status}": count
                    for (method, status), count in self._request_counts.items()
                },
                "request_duration_ms": {
                    f"{method}:{status}": {
                        "count": int(values[0]),
                        "total": values[1],
                        "max": values[2],
                    }
                    for (method, status), values in self._request_durations.items()
                },
                "security_events": dict(self._security_event_counts),
                "ai_events": dict(self._ai_event_counts),
            }


metrics = ApplicationMetrics()


def normalize_http_method(method: str) -> str:
    """Normalize methods to a bounded label shared by metrics and logs."""
    normalized = method.upper()
    return normalized if normalized in _HTTP_METHODS else "OTHER"


def security_audit_event(
    event: str,
    *,
    success: bool,
    user_id: str | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
) -> None:
    """Audit outcomes with keyed references, without raw identities or browser metadata.

    References correlate events under the current server key; they are pseudonyms,
    not anonymous data. User-agent text is accepted for caller compatibility but omitted.
    """
    if event not in _SECURITY_EVENTS:
        return

    context = {
        "event": event,
        "success": success,
        "request_id": request_id_context.get(),
    }
    if user_id:
        context["user_ref"] = _audit_reference("user", user_id)
    if client_ip:
        context["client_ref"] = _audit_reference("client", client_ip)
    if reason:
        context["reason"] = reason[:64]

    metrics.record_security_event(event)
    logging.getLogger("shopsmart.security").log(
        logging.INFO if success else logging.WARNING,
        "security_event",
        extra=context,
    )


def _audit_reference(kind: str, value: str) -> str:
    # Keying prevents offline IP enumeration; domains prevent cross-field correlation.
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        f"security-audit:v1:{kind}:{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class RequestObservabilityMiddleware:
    """Add a validated request ID and record safe request metrics/logs."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming_id = next(
            (
                value.decode("latin-1")
                for key, value in scope.get("headers", [])
                if key.lower() == b"x-request-id"
            ),
            "",
        )
        request_id = incoming_id if _REQUEST_ID_PATTERN.fullmatch(incoming_id) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        method = str(scope.get("method", "OTHER")).upper()
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = (time.perf_counter() - started_at) * 1000
            route = getattr(scope.get("route"), "path", "unmatched")
            metrics.record_request(method, status_code, duration_ms)
            logging.getLogger("shopsmart.request").info(
                "request_completed",
                extra={
                    "event": "request_completed",
                    "method": normalize_http_method(method),
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 3),
                    "request_id": request_id,
                },
            )
            request_id_context.reset(token)
