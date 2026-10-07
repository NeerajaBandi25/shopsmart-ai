"""Security and rendering checks for semantic order notification templates."""

import pytest

from src.core.config import settings
from src.emails.templates.order import OrderEmail, OrderLine, render_order_email


def test_html_and_text_include_authoritative_values_and_status() -> None:
    subject, text, html = render_order_email(
        "payment_success",
        OrderEmail(
            order_number="SS-20261004-AB12CD34",
            lines=(OrderLine("Laptop", 2, 139980),),
            subtotal_cents=139980,
            discount_cents=10000,
            total_cents=129980,
            delivery_summary="Hyderabad, Telangana",
            status_label="Paid",
        ),
    )
    assert "Payment received" in subject
    assert "Laptop x 2" in text
    assert "₹1,299.80" in html
    assert "Hyderabad" in html and "Paid" in text
    assert "/orders" in html


def test_html_escapes_untrusted_values_in_both_representations() -> None:
    _, text, html = render_order_email(
        "order_confirmation",
        OrderEmail(
            order_number="SS-<unsafe>",
            recipient_name='<img src=x onerror="alert(1)">',
            lines=(OrderLine('<script>alert("x")</script>', 1, 100),),
            subtotal_cents=100,
            discount_cents=0,
            total_cents=100,
            delivery_summary="<svg/onload=alert(1)>",
        ),
    )
    assert "<script>" not in html and "<img src=x" not in html and "<svg" not in html
    assert "<script>" in text


def test_cta_rejects_external_and_injection_urls() -> None:
    data = OrderEmail("SS-1", (), 0, 0, 0, order_url="//evil.example")
    with pytest.raises(ValueError, match="app-owned"):
        render_order_email("order_confirmation", data)


def test_text_email_fields_cannot_inject_new_lines() -> None:
    _, text, _ = render_order_email(
        "order_confirmation",
        OrderEmail(
            order_number="SS-1\nBcc: attacker@example.test",
            recipient_name="Shopper\r\nBcc: attacker@example.test",
            lines=(OrderLine("Phone\nStatus: refunded", 1, 100),),
            subtotal_cents=100,
            discount_cents=0,
            total_cents=100,
            delivery_summary="City\nPayment: refunded",
        ),
    )
    assert "\nBcc:" not in text
    assert "Shopper Bcc: attacker@example.test" in text
    assert "Phone Status: refunded" in text
    assert "Delivery: City Payment: refunded" in text


def test_http_local_app_url_is_allowed_only_in_development(monkeypatch) -> None:
    monkeypatch.setattr(settings, "public_app_url", "http://localhost:3000")
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(ValueError, match="HTTPS"):
        render_order_email("order_confirmation", OrderEmail("SS-1", (), 0, 0, 0))


def test_template_rejects_invalid_money_values() -> None:
    data = OrderEmail("SS-1", (OrderLine("item", 0, 1),), 1, 0, 1)
    with pytest.raises(ValueError, match="line values"):
        render_order_email("order_confirmation", data)

    inconsistent = OrderEmail("SS-1", (OrderLine("item", 1, 100),), 100, 10, 95)
    with pytest.raises(ValueError, match="inconsistent"):
        render_order_email("order_confirmation", inconsistent)
