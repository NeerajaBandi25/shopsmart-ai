"""Provider boundary and explicitly local-only console/capture adapters."""

import asyncio
import logging
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import httpx

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


class ResendEmailProvider:
    """Transactional delivery through Resend's HTTPS API."""

    name = "resend"
    endpoint = "https://api.resend.com/emails"

    def __init__(self, *, api_key: str, from_address: str) -> None:
        if not api_key.strip():
            raise RuntimeError("RESEND_API_KEY is required for the selected email provider")
        if not from_address.strip() or "\r" in from_address or "\n" in from_address:
            raise RuntimeError("EMAIL_FROM_ADDRESS must be a valid configured sender")
        self._api_key = api_key.strip()
        self._from_address = from_address.strip()

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        """Send one message; normalize failures without retaining provider response content."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
                response = await client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "from": self._from_address,
                        "to": [recipient],
                        "subject": subject,
                        "text": text_body,
                        "html": html_body,
                    },
                )
        except httpx.TimeoutException as exc:
            raise EmailDeliveryError("provider_timeout", transient=True) from exc
        except httpx.RequestError as exc:
            raise EmailDeliveryError("provider_connection_failed", transient=True) from exc

        if response.is_success:
            return
        status = response.status_code
        raise EmailDeliveryError(
            f"provider_http_{status}", transient=status == 429 or status >= 500
        )


class SMTPEmailProvider:
    """SMTP delivery for local testing with a mailbox-owned app password."""

    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        use_ssl: bool = False,
    ) -> None:
        if not host.strip() or not 1 <= port <= 65535:
            raise RuntimeError("SMTP_HOST and a valid SMTP_PORT are required")
        if not username.strip() or not password:
            raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD are required")
        if not from_address.strip() or "\r" in from_address or "\n" in from_address:
            raise RuntimeError("EMAIL_FROM_ADDRESS must be a valid configured sender")
        self._host = host.strip()
        self._port = port
        self._username = username.strip()
        self._password = password
        self._from_address = from_address.strip()
        self._use_ssl = use_ssl

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        if "\r" in subject or "\n" in subject:
            raise EmailDeliveryError("invalid_subject", transient=False)
        message = EmailMessage()
        message["From"] = self._from_address
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        context = ssl.create_default_context()
        try:
            if self._use_ssl:
                client = smtplib.SMTP_SSL(self._host, self._port, timeout=15, context=context)
            else:
                client = smtplib.SMTP(self._host, self._port, timeout=15)
            with client:
                if not self._use_ssl:
                    client.ehlo()
                    client.starttls(context=context)
                    client.ehlo()
                client.login(self._username, self._password)
                refused = client.send_message(message)
                if refused:
                    codes = [int(result[0]) for result in refused.values()]
                    transient = any(400 <= code < 500 for code in codes)
                    raise EmailDeliveryError("smtp_recipient_rejected", transient=transient)
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailDeliveryError("smtp_authentication_failed", transient=False) from exc
        except smtplib.SMTPResponseException as exc:
            code = int(exc.smtp_code)
            raise EmailDeliveryError(f"smtp_response_{code}", transient=400 <= code < 500) from exc
        except (smtplib.SMTPServerDisconnected, TimeoutError, OSError) as exc:
            raise EmailDeliveryError("smtp_connection_failed", transient=True) from exc


def create_email_provider(name: str, *, app_env: str, **credentials: str | None) -> EmailProvider:
    """Select a provider without ever treating a missing external adapter as success."""
    normalized = name.strip().lower()
    if normalized in {"console", "capture"}:
        if app_env.lower() not in {"development", "dev", "test", "local"}:
            raise RuntimeError(
                "console/capture email providers are restricted to local and test environments"
            )
        return ConsoleEmailProvider() if normalized == "console" else CaptureEmailProvider()
    if normalized == "resend":
        return ResendEmailProvider(
            api_key=credentials.get("resend_api_key") or "",
            from_address=credentials.get("from_address") or "",
        )
    if normalized == "smtp":
        try:
            port = int(credentials.get("smtp_port") or "587")
        except ValueError as exc:
            raise RuntimeError("SMTP_PORT must be a valid port number") from exc
        return SMTPEmailProvider(
            host=credentials.get("smtp_host") or "",
            port=port,
            username=credentials.get("smtp_username") or "",
            password=credentials.get("smtp_password") or "",
            from_address=credentials.get("from_address") or "",
            use_ssl=(credentials.get("smtp_use_ssl") or "false").strip().lower()
            in {"1", "true", "yes", "on"},
        )
    if normalized == "mailtrap":
        raise RuntimeError("mailtrap adapter is not installed; refusing to fake delivery")
    raise RuntimeError("Unsupported email provider")
