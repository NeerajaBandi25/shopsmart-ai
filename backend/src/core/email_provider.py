"""Email provider abstraction for sending notifications."""

from abc import ABC, abstractmethod


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    def send_notification(self, recipient: str, subject: str, body: str) -> bool:
        """Send email notification.

        Args:
            recipient: Email address of recipient
            subject: Email subject
            body: Email body

        Returns:
            bool: True if sent successfully, False otherwise
        """
        pass
