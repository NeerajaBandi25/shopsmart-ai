"""ASGI app for isolated browser checkout QA with a local fake payment provider."""

from uuid import uuid4

from src.main import app
from src.services.payment_provider import CheckoutSession, get_payment_provider


class LocalFakePaymentProvider:
    """Return a Stripe-shaped destination without making an external request."""

    name = "local-fake-e2e"

    def is_configured(self) -> bool:
        return True

    def validate_checkout_configuration(self) -> None:
        return None

    async def create_checkout_session(self, **kwargs) -> CheckoutSession:
        session_id = f"cs_test_local_{uuid4().hex}"
        return CheckoutSession(
            session_id=session_id,
            checkout_url=f"https://checkout.stripe.com/c/pay/{session_id}",
        )


app.dependency_overrides[get_payment_provider] = LocalFakePaymentProvider
