"""Lazy model exports avoid package-init cycles between model modules."""

__all__ = ["NotificationOutbox", "Payment", "PaymentWebhookEvent", "ShopperPreference"]


def __getattr__(name: str):
    if name == "NotificationOutbox":
        from src.emails.model import NotificationOutbox

        return NotificationOutbox
    if name in {"Payment", "PaymentWebhookEvent"}:
        from src.models.payment import Payment, PaymentWebhookEvent

        return {"Payment": Payment, "PaymentWebhookEvent": PaymentWebhookEvent}[name]
    if name == "ShopperPreference":
        from src.models.shopper_preference import ShopperPreference

        return ShopperPreference
    raise AttributeError(name)
