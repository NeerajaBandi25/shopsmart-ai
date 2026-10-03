import pytest

from src.services.assistant_router import AssistantIntent, route_assistant_message


def test_routes_all_supported_intents():
    examples = {
        "Hello": AssistantIntent.GREETING,
        "How can you help?": AssistantIntent.HELP,
        "Find products under ₹5,000": AssistantIntent.PRODUCT_SEARCH,
        "Compare these two": AssistantIntent.PRODUCT_COMPARE,
        "Which one is cheaper?": AssistantIntent.PRODUCT_COMPARE,
        "Which of these laptops is cheaper?": AssistantIntent.PRODUCT_COMPARE,
        "Any active offers?": AssistantIntent.PROMOTIONS,
        "Can I use SAVE10?": AssistantIntent.PROMOTIONS,
        "Apply coupon SAVE10": AssistantIntent.COUPON_APPLY,
        "Remove my coupon": AssistantIntent.COUPON_REMOVE,
        "What's in my cart?": AssistantIntent.CART_QUERY,
        "Add to cart": AssistantIntent.CART_ACTION,
        "Track my order": AssistantIntent.ORDER_QUERY,
        "Where is my last order?": AssistantIntent.ORDER_QUERY,
        "What is the return policy?": AssistantIntent.POLICY_QUERY,
        "Contact customer service": AssistantIntent.SUPPORT_QUERY,
        "Write me a poem": AssistantIntent.UNSUPPORTED,
    }

    for message, expected in examples.items():
        assert route_assistant_message(message).intent is expected


def test_coupon_routes_extract_only_bounded_coupon_codes():
    check = route_assistant_message("Can I use SAVE10?")
    apply = route_assistant_message("Apply coupon save10")

    assert check.coupon_code == "SAVE10"
    assert apply.coupon_code == "SAVE10"


def test_catalog_filters_use_current_supported_fields():
    route = route_assistant_message("Find products under $49.99 that are in stock")

    assert route.intent is AssistantIntent.PRODUCT_SEARCH
    assert route.max_price_cents == 4999
    assert route.in_stock_only is True


@pytest.mark.parametrize(
    ("question", "category"),
    [
        ("show me laptops under 60000", "laptops"),
        ("show me laptop under 60000", "laptops"),
        ("laptops under 60000", "laptops"),
        ("show me mobile phones under 30000", "phones"),
        ("show me mobiles under 30000", "phones"),
        ("show me shoes under 5000", "footwear"),
    ],
)
def test_category_aliases_route_to_canonical_structured_filter(question, category):
    route = route_assistant_message(question)

    assert route.intent is AssistantIntent.PRODUCT_SEARCH
    assert route.category == category
    assert route.max_price_cents in {500_000, 3_000_000, 5_000_000, 6_000_000}
    assert route.unsupported_category is False


def test_generic_price_search_remains_category_unrestricted():
    route = route_assistant_message("show me products under 5000")

    assert route.intent is AssistantIntent.PRODUCT_SEARCH
    assert route.category is None
    assert route.max_price_cents == 500_000


def test_unknown_or_conflicting_explicit_categories_are_unsupported():
    for question in (
        "show me category=tablets under 60000",
        "show me tablets under 60000",
        "find electronics under 30000",
        "show me laptops and phones under 60000",
    ):
        route = route_assistant_message(question)

        assert route.intent is AssistantIntent.UNSUPPORTED
        assert route.unsupported_category is True


def test_minimum_and_maximum_price_constraints_are_structural():
    route = route_assistant_message("find laptops above 1000 and under 60000")

    assert route.category == "laptops"
    assert route.min_price_cents == 100_000
    assert route.max_price_cents == 6_000_000


def test_rupee_grouped_amounts_are_parsed_as_inr():
    route = route_assistant_message("Find in-stock products under ₹5,000")

    assert route.intent is AssistantIntent.PRODUCT_SEARCH
    assert route.max_price_cents == 500_000
    assert route.in_stock_only is True
    assert route.invalid_price_filter is False


def test_ambiguous_mutation_is_not_inferred():
    route = route_assistant_message("I like that one")

    assert route.intent is AssistantIntent.UNSUPPORTED
    assert route.max_price_cents is None


def test_cart_how_to_question_does_not_route_to_mutation():
    route = route_assistant_message("How do I add 2 headphones to my cart?")

    assert route.intent is AssistantIntent.UNSUPPORTED


def test_explicit_quantity_cart_action_is_routed():
    route = route_assistant_message("Add 2 headphones to my cart")

    assert route.intent is AssistantIntent.CART_ACTION


def test_invalid_price_constraints_are_not_silently_ignored():
    for message in (
        "Find products under $999999999999",
        "Show products under $1,000",
        "Find headphones below $49.999",
    ):
        route = route_assistant_message(message)

        assert route.intent is AssistantIntent.PRODUCT_SEARCH
        assert route.invalid_price_filter is True
        assert route.max_price_cents is None
