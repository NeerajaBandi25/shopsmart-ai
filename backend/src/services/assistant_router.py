"""Deterministic intent and supported catalog-filter extraction."""

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class AssistantIntent(StrEnum):
    GREETING = "GREETING"
    HELP = "HELP"
    PRODUCT_SEARCH = "PRODUCT_SEARCH"
    PRODUCT_COMPARE = "PRODUCT_COMPARE"
    PROMOTIONS = "PROMOTIONS"
    COUPON_APPLY = "COUPON_APPLY"
    COUPON_REMOVE = "COUPON_REMOVE"
    CART_QUERY = "CART_QUERY"
    CART_ACTION = "CART_ACTION"
    ORDER_QUERY = "ORDER_QUERY"
    POLICY_QUERY = "POLICY_QUERY"
    SUPPORT_QUERY = "SUPPORT_QUERY"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class AssistantRoute:
    intent: AssistantIntent
    max_price_cents: int | None = None
    in_stock_only: bool = False
    invalid_price_filter: bool = False
    category: str | None = None
    min_price_cents: int | None = None
    unsupported_category: bool = False
    coupon_code: str | None = None


_MAX_PRICE = re.compile(
    r"\b(?:under|below|less than|up to|at most|maximum(?: price)?(?: of)?)\s*(?P<currency>[$₹])?\s*(?P<amount>\d+(?:,\d{2,3})*(?:\.\d{1,2})?)(?![\d,.])\b",
    re.IGNORECASE,
)
_MIN_PRICE = re.compile(
    r"\b(?:over|above|more than|greater than|at least|minimum(?: price)?(?: of)?)\s*(?P<currency>[$₹])?\s*(?P<amount>\d+(?:,\d{2,3})*(?:\.\d{1,2})?)(?![\d,.])\b",
    re.IGNORECASE,
)
_IN_STOCK = re.compile(r"\bin[- ]stock\b", re.IGNORECASE)
_PRICE_CUE = re.compile(
    r"\b(?:under|below|less than|up to|at most|maximum(?: price)?(?: of)?|over|above|more than|greater than|at least|minimum(?: price)?(?: of)?)\b",
    re.IGNORECASE,
)
_CATEGORY_CUE = re.compile(r"\bcategory\s*(?:=|:|is)\s*([a-z][a-z-]*)\b", re.IGNORECASE)
CATEGORY_ALIASES = {
    "laptop": "laptops",
    "laptops": "laptops",
    "mobile": "phones",
    "mobiles": "phones",
    "mobile phone": "phones",
    "mobile phones": "phones",
    "phone": "phones",
    "phones": "phones",
    "accessory": "accessories",
    "accessories": "accessories",
    "charger": "accessories",
    "chargers": "accessories",
    "shoe": "footwear",
    "shoes": "footwear",
    "footwear": "footwear",
    "fashion": "fashion",
    "clothing": "fashion",
    "appliance": "appliances",
    "appliances": "appliances",
    "home": "home",
    "beauty": "beauty",
    "grocery": "groceries",
    "groceries": "groceries",
}
_UNSUPPORTED_CATEGORY_ALIASES = {"electronic", "electronics", "tablet", "tablets"}
_COUPON_LABEL = re.compile(
    r"\b(?:coupon(?:\s+code)?|code)\s*(?:(?:is|:|=)\s*)?([A-Z0-9][A-Z0-9_-]{0,31})\b",
    re.IGNORECASE,
)
_COUPON_ACTION = re.compile(r"\b(?:use|apply|redeem)\s+([A-Z0-9][A-Z0-9_-]{0,31})\b", re.IGNORECASE)


def _category_filter(text: str) -> tuple[str | None, bool]:
    explicit = _CATEGORY_CUE.search(text)
    if explicit:
        value = explicit.group(1).lower()
        return CATEGORY_ALIASES.get(value), value not in CATEGORY_ALIASES

    if any(
        re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text)
        for alias in _UNSUPPORTED_CATEGORY_ALIASES
    ):
        return None, True

    matches = {
        category
        for alias, category in CATEGORY_ALIASES.items()
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text)
    }
    if len(matches) > 1:
        return None, True
    return (next(iter(matches)) if matches else None), False


def _coupon_code(text: str) -> str | None:
    match = _COUPON_LABEL.search(text) or _COUPON_ACTION.search(text)
    return match.group(1).upper() if match else None


def _price_cents(match: re.Match[str]) -> int | None:
    amount = match.group("amount")
    if "," in amount and match.group("currency") != "₹":
        return None
    return int(Decimal(amount.replace(",", "")) * 100)


def route_assistant_message(message: str) -> AssistantRoute:
    text = " ".join(message.lower().split())
    if not text:
        return AssistantRoute(AssistantIntent.UNSUPPORTED)

    if re.fullmatch(r"(?:hi|hello|hey|good morning|good afternoon|good evening)[!. ]*", text):
        return AssistantRoute(AssistantIntent.GREETING)
    if text in {"help", "help!", "help me"} or any(
        term in text for term in ("what can you do", "how can you help")
    ):
        return AssistantRoute(AssistantIntent.HELP)
    if re.search(r"\b(?:remove|clear|delete|forget)\b.{0,30}\bcoupon\b", text):
        return AssistantRoute(AssistantIntent.COUPON_REMOVE)
    coupon_code = _coupon_code(text)
    if coupon_code and re.search(r"\b(?:apply|redeem)\b", text):
        return AssistantRoute(AssistantIntent.COUPON_APPLY, coupon_code=coupon_code)
    if coupon_code:
        return AssistantRoute(AssistantIntent.PROMOTIONS, coupon_code=coupon_code)
    if any(
        term in text
        for term in (
            "return",
            "refund",
            "warranty",
            "shipping",
            "delivery policy",
            "payment",
            "loyalty",
            "buying guide",
            "faq",
        )
    ):
        return AssistantRoute(AssistantIntent.POLICY_QUERY)
    if any(
        term in text
        for term in ("customer service", "contact support", "support team", "technical support")
    ):
        return AssistantRoute(AssistantIntent.SUPPORT_QUERY)
    if any(
        term in text for term in ("promotion", "promotions", "discount", "coupon", "deal", "offer")
    ):
        category, unsupported_category = _category_filter(text)
        if unsupported_category:
            return AssistantRoute(
                AssistantIntent.UNSUPPORTED,
                unsupported_category=True,
            )
        return AssistantRoute(
            AssistantIntent.PROMOTIONS,
            category=category,
            coupon_code=coupon_code,
        )
    if any(
        term in text
        for term in (
            "my orders",
            "order status",
            "track my order",
            "where is my order",
            "where's my order",
            "where is my last order",
            "where's my last order",
            "order history",
            "check my order",
        )
    ):
        return AssistantRoute(AssistantIntent.ORDER_QUERY)
    is_how_to_question = text.startswith(("how do i ", "how can i ", "should i "))
    if is_how_to_question and "cart" in text:
        return AssistantRoute(AssistantIntent.UNSUPPORTED)
    is_cart_mutation = any(
        re.search(pattern, text)
        for pattern in (
            r"\badd(?:\s+\d{1,2})?.{0,80}\bto\s+(?:my\s+)?cart\b",
            r"\bput\b.{0,80}\bin\s+(?:my\s+)?cart\b",
            r"\bremove\b.{0,80}\bfrom\s+(?:my\s+)?cart\b",
            r"\b(?:remove|take)\s+(?:this|that|it)\s+out\s+of\s+(?:my\s+)?cart\b",
        )
    )
    if is_cart_mutation and not is_how_to_question:
        return AssistantRoute(AssistantIntent.CART_ACTION)
    if any(
        term in text
        for term in (
            "my cart",
            "shopping cart",
            "cart contents",
            "what's in my cart",
            "what is in my cart",
            "show cart",
            "view cart",
        )
    ):
        return AssistantRoute(AssistantIntent.CART_QUERY)
    if any(term in text for term in ("compare", " versus ", " vs ")) or re.search(
        r"\bwhich\b.{0,50}\b(?:cheaper|cheapest|less expensive|lower[- ]priced)\b",
        text,
    ):
        return AssistantRoute(
            AssistantIntent.PRODUCT_COMPARE, in_stock_only=bool(_IN_STOCK.search(text))
        )
    if (
        any(
            term in text
            for term in (
                "find",
                "search",
                "show",
                "looking for",
                "recommend",
                "products",
                "product",
            )
        )
        or _CATEGORY_CUE.search(text)
        or _category_filter(text)[0] is not None
    ):
        category, unsupported_category = _category_filter(text)
        if unsupported_category:
            return AssistantRoute(
                AssistantIntent.UNSUPPORTED,
                unsupported_category=True,
            )
        max_match = _MAX_PRICE.search(text)
        min_match = _MIN_PRICE.search(text)
        max_price_cents = None
        min_price_cents = None
        invalid_price_filter = bool(_PRICE_CUE.search(text)) and not (max_match or min_match)
        if max_match:
            max_price_cents = _price_cents(max_match)
            if max_price_cents is None or max_price_cents > 2_147_483_647:
                invalid_price_filter = True
                max_price_cents = None
        if min_match:
            min_price_cents = _price_cents(min_match)
            if min_price_cents is None or min_price_cents > 2_147_483_647:
                invalid_price_filter = True
                min_price_cents = None
        if (
            max_price_cents is not None
            and min_price_cents is not None
            and min_price_cents > max_price_cents
        ):
            invalid_price_filter = True
        if _CATEGORY_CUE.search(text) and category is None:
            return AssistantRoute(
                AssistantIntent.UNSUPPORTED,
                unsupported_category=True,
            )
        return AssistantRoute(
            AssistantIntent.PRODUCT_SEARCH,
            max_price_cents=max_price_cents,
            in_stock_only=bool(_IN_STOCK.search(text)) or "available" in text,
            invalid_price_filter=invalid_price_filter,
            category=category,
            min_price_cents=min_price_cents,
        )
    return AssistantRoute(AssistantIntent.UNSUPPORTED)
