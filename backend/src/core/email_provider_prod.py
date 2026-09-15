"""Production email provider stub."""

import logging

from src.core.email_provider import EmailProvider

logger = logging.getLogger(__name__)


class ProductionEmailProvider(EmailProvider):
    """Production email provider stub.

    This is a placeholder implementation for future integration with
    SendGrid, AWS SES, or other email service providers.
    Email delivery is out of scope for v1; this stub allows infrastructure readiness.
    """

    def send_notification(self, recipient: str, subject: str, body: str) -> bool:
        """Send email notification (stub implementation).

        Args:
            recipient: Email address of recipient
            subject: Email subject
            body: Email body

        Returns:
            bool: Always returns True (ready for future integration)
        """
        logger.info(
            f"[STUB] Would send email to {recipient} with subject: {subject}"
        )
        # Future implementation: Integrate with SendGrid, AWS SES, etc.
        return True
