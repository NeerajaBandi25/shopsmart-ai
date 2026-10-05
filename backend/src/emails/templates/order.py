"""Escaped HTML and plain-text order notification templates."""

from dataclasses import dataclass
from html import escape
from typing import Literal
from urllib.parse import urlsplit

from src.core.config import settings


TemplateName = Literal[
    "order_confirmation", "payment_success", "payment_failed", "order_cancelled", "order_status"
]


@dataclass(frozen=True)
class OrderLine:
    name: str
    quantity: int
    line_total_cents: int


@dataclass(frozen=True)
class OrderEmail:
    order_number: str
    lines: tuple[OrderLine, ...]
    subtotal_cents: int
    discount_cents: int
    total_cents: int
    recipient_name: str = ""
    delivery_summary: str | None = None
    order_url: str = "/orders"
    status_label: str | None = None


_COPY: dict[TemplateName, tuple[str, str]] = {
    "order_confirmation": ("Your ShopSmart order is confirmed", "Order confirmed"),
    "payment_success": ("Payment received for your ShopSmart order", "Payment received"),
    "payment_failed": ("Action needed for your ShopSmart order", "Payment needs attention"),
    "order_cancelled": ("Your ShopSmart order was cancelled", "Order cancelled"),
    "order_status": ("An update on your ShopSmart order", "Order update"),
}


def _money(cents: int) -> str:
    return f"₹{cents / 100:,.2f}"


def _validated_url(url: str) -> str:
    # Relative paths prevent an untrusted payload from turning this into an open redirect.
    if not url.startswith("/orders") or url.startswith("//") or "\r" in url or "\n" in url:
        raise ValueError("order_url must be an app-owned order path")
    base_url = settings.public_app_url.rstrip("/")
    parts = urlsplit(base_url)
    local_http_allowed = settings.app_env.strip().lower() in {"local", "dev", "development", "test"}
    local_host = (parts.hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}
    if (
        parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or "\\" in base_url
        or not parts.hostname
        or (
            parts.scheme != "https"
            and not (parts.scheme == "http" and local_host and local_http_allowed)
        )
    ):
        raise ValueError("PUBLIC_APP_URL must use HTTPS outside local development")
    return f"{base_url}{url}"


def _plain(value: str) -> str:
    """Keep user/catalog values on one line in text email clients."""
    return " ".join(
        "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value).split()
    )


def render_order_email(template: TemplateName, data: OrderEmail) -> tuple[str, str, str]:
    """Render subject, plain text, and HTML from a semantic message payload."""
    if template not in _COPY:
        raise ValueError("Unsupported email template")
    if not data.order_number or len(data.order_number) > 80:
        raise ValueError("A customer-facing order number is required")
    if any(line.quantity < 1 or line.line_total_cents < 0 for line in data.lines):
        raise ValueError("Order line values are invalid")
    if min(data.subtotal_cents, data.discount_cents, data.total_cents) < 0:
        raise ValueError("Order totals cannot be negative")
    if (
        data.discount_cents > data.subtotal_cents
        or data.total_cents != data.subtotal_cents - data.discount_cents
        or sum(line.line_total_cents for line in data.lines) != data.subtotal_cents
    ):
        raise ValueError("Order totals are inconsistent")

    title, intro = _COPY[template]
    plain_name = _plain(data.recipient_name)
    safe_name = escape(data.recipient_name, quote=True)
    greeting = f"Hello {safe_name}," if safe_name else "Hello,"
    plain_greeting = f"Hello {plain_name}," if plain_name else "Hello,"
    safe_number = escape(data.order_number, quote=True)
    url = escape(_validated_url(data.order_url), quote=True)
    line_html = "".join(
        '<tr><td style="padding:10px 0;border-bottom:1px solid #eee;">'
        f"{escape(line.name, quote=True)} × {line.quantity}</td>"
        f'<td style="padding:10px 0;text-align:right;border-bottom:1px solid #eee;">{_money(line.line_total_cents)}</td></tr>'
        for line in data.lines
    )
    line_text = (
        "\n".join(
            f"- {_plain(line.name)} x {line.quantity}: {_money(line.line_total_cents)}"
            for line in data.lines
        )
        or "No item details available."
    )
    delivery_text = f"\nDelivery: {_plain(data.delivery_summary)}" if data.delivery_summary else ""
    delivery_html = (
        f"<p><strong>Delivery</strong><br>{escape(data.delivery_summary, quote=True)}</p>"
        if data.delivery_summary
        else ""
    )
    status = f"\nStatus: {_plain(data.status_label)}" if data.status_label else ""
    status_html = (
        f"<p><strong>Status:</strong> {escape(data.status_label, quote=True)}</p>"
        if data.status_label
        else ""
    )
    plain = (
        f"{title}\n\n{plain_greeting}\n{intro}. Order {_plain(data.order_number)}.\n\n{line_text}\n\n"
        f"Subtotal: {_money(data.subtotal_cents)}\nDiscount: -{_money(data.discount_cents)}\n"
        f"Total: {_money(data.total_cents)}{delivery_text}{status}\n\n"
        f"View your order: {_plain(data.order_url)}\n\nShopSmart AI"
    )
    html = (
        '<!doctype html><html><body style="margin:0;background:#f6f3ee;color:#20211f;'
        'font-family:Arial,sans-serif;"><table role="presentation" width="100%"><tr><td align="center" '
        'style="padding:28px 12px;"><table role="presentation" width="600" style="max-width:600px;'
        'background:#fff;padding:32px;border-radius:12px;"><tr><td>'
        '<p style="letter-spacing:.14em;color:#702943;font-weight:bold;">SHOPSMART AI</p>'
        f"<h1>{escape(title)}</h1><p>{greeting}</p><p>{escape(intro)}. Your order <strong>{safe_number}</strong>.</p>"
        '<table role="presentation" width="100%"><tbody>' + line_html + "</tbody></table>"
        f"<p>Subtotal: {_money(data.subtotal_cents)}<br>Discount: −{_money(data.discount_cents)}<br>"
        f"<strong>Total: {_money(data.total_cents)}</strong></p>{delivery_html}{status_html}"
        f'<p><a href="{url}" style="display:inline-block;background:#702943;color:white;padding:12px 18px;'
        'border-radius:6px;text-decoration:none;">View your order</a></p>'
        '<p style="color:#666;font-size:12px;">ShopSmart AI · A clearer way to choose</p>'
        "</td></tr></table></td></tr></table></body></html>"
    )
    return title, plain, html
