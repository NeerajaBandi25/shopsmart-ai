"""Mock email provider for testing."""

import logging

from src.core.email_provider import EmailProvider

logger = logging.getLogger(__name__)


class MockEmailProvider(EmailProvider):
    """Mock email provider that stores emails in memory for testing."""

    def __init__(self):
        """Initialize mock provider."""
        self._sent_emails: list[dict] = []

    def send_notification(self, recipient: str, subject: str, body: str) -> bool:
        """Store email in memory instead of sending.

        Args:
            recipient: Email address of recipient
            subject: Email subject
            body: Email body

        Returns:
            bool: Always returns True (simulates successful send)
        """
        email = {
            "recipient": recipient,
            "subject": subject,
            "body": body,
        }
        self._sent_emails.append(email)
        logger.info(f"Mock email sent to {recipient}: {subject}")
        return True

    def get_sent_emails(self) -> list[dict]:
        """Get list of emails sent during tests.

        Returns:
            list[dict]: List of sent email dictionaries
        """
        return self._sent_emails

    def clear_sent_emails(self) -> None:
        """Clear sent emails list."""
        self._sent_emails.clear()
