"""Provider boundary and explicitly local-only console/capture adapters."""

import logging
import re
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Normalized provider failure with a safe machine-readable code."""

    def __init__(self, code: str, *, transient: bool) -> None:
        super().__init__(code)
        self.code = re.sub(r"[^a-zA-Z0-9_.-]", "_", code)[:64] or "delivery_failed"
        self.transient = transient


class EmailProvider(Protocol):
    """Sends rendered messages; provider implementations must not log message content."""

    name: str

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        ...


@dataclass(frozen=True)
class CapturedEmail:
    recipient: str
    subject: str
    text_body: str
    html_body: str


class CaptureEmailProvider:
    """In-memory sink for tests; message bodies are visible only to the test process."""

    name = "capture"

    def __init__(self) -> None:
        self.messages: list[CapturedEmail] = []

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        self.messages.append(CapturedEmail(recipient, subject, text_body, html_body))
        logger.info("email_capture_recorded", extra={"provider": self.name, "template": "rendered"})


class ConsoleEmailProvider:
    """Local-only sink that records metadata and deliberately discards content."""

    name = "console"

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        domain = recipient.rpartition("@")[2].lower() if "@" in recipient else "invalid"
        logger.info(
            "email_console_sink",
            extra={
                "provider": self.name,
                "recipient_domain": domain,
                "subject_length": len(subject),
            },
        )


def create_email_provider(name: str, *, app_env: str, **credentials: str | None) -> EmailProvider:
    """Select a provider without ever treating a missing external adapter as success."""
    normalized = name.strip().lower()
    if normalized in {"console", "capture"}:
        if app_env.lower() not in {"development", "dev", "test", "local"}:
            raise RuntimeError(
                "console/capture email providers are restricted to local and test environments"
            )
        return ConsoleEmailProvider() if normalized == "console" else CaptureEmailProvider()
    if normalized in {"resend", "mailtrap", "smtp"}:
        key_name = {
            "resend": "RESEND_API_KEY",
            "mailtrap": "MAILTRAP_API_TOKEN",
            "smtp": "SMTP_URL",
        }[normalized]
        if not credentials.get(key_name.lower()):
            raise RuntimeError(f"{key_name} is required for the selected email provider")
        raise RuntimeError(f"{normalized} adapter is not installed; refusing to fake delivery")
    raise RuntimeError("Unsupported email provider")
