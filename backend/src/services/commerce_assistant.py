"""Commerce-first assistant orchestration over authoritative ShopSmart services."""

import logging
import re
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppException, NotFoundError
from src.core.observability import metrics, request_id_context
from src.schemas.ai import Citation
from src.services.ai_gateway import ProviderGateway
from src.services.ai_governance import DataClassification
from src.services.ai_repository import ConversationRepository
from src.services.assistant_knowledge import KnowledgeRetrievalService
from src.services.assistant_router import CATEGORY_ALIASES, AssistantIntent, route_assistant_message
from src.services.cart_service import CartService
from src.services.order_service import OrderService
from src.services.product_catalog_service import ProductCatalogService

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "available",
    "find",
    "for",
    "in",
    "me",
    "of",
    "on",
    "product",
    "products",
    "recommend",
    "search",
    "show",
    "some",
    "the",
    "that",
    "to",
    "under",
    "up",
    "with",
    "stock",
    "in-stock",
    "at",
    "most",
    "less",
    "than",
    "below",
    "price",
}


def _log_product_search(
    route,
    *,
    result_count: int,
    duration_ms: float,
    status_code: int = 200,
    error_code: str | None = None,
    error_type: str | None = None,
) -> None:
    context = {
        "event": "assistant_operation",
        "service": "commerce_assistant",
        "tool": "product_search",
        "operation": "product_search",
        "intent": route.intent.value,
        "category": route.category or ("unsupported" if route.unsupported_category else None),
        "min_price_cents": route.min_price_cents,
        "max_price_cents": route.max_price_cents,
        "in_stock_only": route.in_stock_only,
        "result_count": result_count,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 3),
        "request_id": request_id_context.get(),
    }
    if error_code:
        context["error_code"] = error_code
    if error_type:
        context["error_type"] = error_type
    logging.getLogger("shopsmart.assistant").log(
        logging.WARNING if status_code >= 400 else logging.INFO,
        "assistant_operation_completed" if status_code < 400 else "assistant_operation_rejected",
        extra=context,
    )


class CommerceAssistantService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.conversations = ConversationRepository(db)
        self.catalog = ProductCatalogService(db)
        self.cart = CartService(db)
        self.orders = OrderService(db)
        self.knowledge = KnowledgeRetrievalService(db)
        self.gateway = ProviderGateway()

    async def answer(
        self, user_id: UUID, question: str, conversation_id: UUID | None = None
    ) -> dict:
        question = question.strip()
        route = route_assistant_message(question)
        if route.invalid_price_filter:
            _log_product_search(
                route,
                result_count=0,
                duration_ms=0,
                status_code=422,
                error_code="invalid_price_filter",
                error_type="AppException",
            )
            raise AppException(
                "Price filter is invalid or exceeds the supported range",
                422,
                "invalid_price_filter",
            )
        if route.unsupported_category:
            _log_product_search(
                route,
                result_count=0,
                duration_ms=0,
                error_code="unsupported_category",
            )
        conversation = (
            await self.conversations.get_owned(conversation_id, user_id)
            if conversation_id
            else None
        )
        if conversation_id and not conversation:
            raise NotFoundError("Conversation not found", "conversation_not_found")
        if conversation is None:
            conversation = await self.conversations.create(user_id, question[:80])

        data: dict | None = None
        citations: list[Citation] = []
        answerable = True
        reason: str | None = None
        if route.intent is AssistantIntent.GREETING:
            answer = (
                "Hi! I can help you find products, compare options, check offers, manage your "
                "cart, track orders, and answer ShopSmart policy questions."
            )
        elif route.intent is AssistantIntent.HELP:
            answer = (
                "Ask me to find or compare products, check offers, review your cart or orders, "
                "or look up a ShopSmart policy."
            )
        elif route.intent is AssistantIntent.PRODUCT_SEARCH:
            terms = self._search_terms(question, route.category)
            search_started = time.perf_counter()
            products = await self.catalog.search_products(
                query_text=" ".join(terms) or None,
                category=route.category,
                min_price_cents=route.min_price_cents,
                max_price_cents=route.max_price_cents,
                in_stock_only=route.in_stock_only,
            )
            _log_product_search(
                route,
                result_count=len(products),
                duration_ms=(time.perf_counter() - search_started) * 1000,
            )
            data = {"products": [self._product_data(item) for item in products]}
            conversation.context = {
                **(conversation.context or {}),
                "product_ids": [str(item.id) for item in products[:20]],
            }
            conversation.context.pop("comparison_product_ids", None)
            conversation.context.pop("selected_product_id", None)
            if products:
                answer = f"I found {len(products)} product(s) matching your request."
            else:
                answer = "I couldn't find products matching that."
                reason = "NO_RESULTS"
        elif route.intent is AssistantIntent.PRODUCT_COMPARE:
            context = conversation.context or {}
            result_key = (
                "comparison_product_ids" if context.get("comparison_product_ids") else "product_ids"
            )
            products = await self._products_for_context_key(context, result_key)
            products = self._select_comparison_products(question, products)
            if len(products) < 2:
                answer = (
                    "Search for products first, then tell me which results you'd like to compare."
                )
            else:
                compared = products[:5]
                data = {"products": [self._product_data(item) for item in compared]}
                conversation.context = {
                    **context,
                    "comparison_product_ids": [str(item.id) for item in compared],
                }
                if self._asks_for_cheapest(question):
                    cheapest = min(compared, key=lambda item: item.price)
                    equally_priced = sum(item.price == cheapest.price for item in compared) > 1
                    if equally_priced:
                        conversation.context.pop("selected_product_id", None)
                        answer = f"These options are tied at {self._format_price(cheapest.price)}."
                    else:
                        conversation.context["selected_product_id"] = str(cheapest.id)
                        answer = (
                            f"{cheapest.name} is the lower-priced option at "
                            f"{self._format_price(cheapest.price)}."
                        )
                else:
                    conversation.context.pop("selected_product_id", None)
                    answer = (
                        f"Here are {len(compared)} products from your recent results to compare."
                    )
        elif route.intent is AssistantIntent.PROMOTIONS:
            answer = "I couldn't find an active offer that applies to this request."
        elif route.intent is AssistantIntent.CART_QUERY:
            cart = await self.cart.get_cart(user_id)
            data = {"cart": self._cart_data(cart)}
            answer = self._cart_summary(cart)
        elif route.intent is AssistantIntent.CART_ACTION:
            product = await self._resolve_product(question, conversation.context)
            if product is None:
                answer = (
                    "Search for a product first, then name the result you want to add or remove."
                )
            elif re.search(r"\bremove\b|\btake\s+(?:this|that|it)\s+out\b", question, re.I):
                data = {
                    "cart": self._cart_data(
                        await self.cart.remove_item(user_id, product.id, commit=False)
                    )
                }
                answer = f"Removed {product.name} from your cart."
            else:
                quantity_match = re.match(r"\s*(?:please\s+)?add\s+(\d{1,2})\b", question, re.I)
                quantity = int(quantity_match.group(1)) if quantity_match else 1
                data = {
                    "cart": self._cart_data(
                        await self.cart.add_item(user_id, product.id, quantity, commit=False)
                    )
                }
                answer = f"Added {quantity} {product.name} to your cart."
        elif route.intent is AssistantIntent.ORDER_QUERY:
            orders = await self.orders.get_user_orders(user_id)
            is_last_order = "last order" in question.lower()
            visible_orders = orders[:1] if is_last_order else orders[:20]
            data = {
                "orders": [
                    {
                        "id": str(order.id),
                        "status": order.status,
                        "total_cents": order.total_cents,
                        "created_at": order.created_at.isoformat(),
                        "items": [
                            {"name": item.product_name, "quantity": item.quantity}
                            for item in order.items
                        ],
                    }
                    for order in visible_orders
                ]
            }
            answer = (
                "Here is your last order."
                if visible_orders and is_last_order
                else "Here are your recent orders."
                if visible_orders
                else "I couldn't find an order in your account."
            )
            if not orders:
                reason = "NO_ORDER"
        elif route.intent in {AssistantIntent.POLICY_QUERY, AssistantIntent.SUPPORT_QUERY}:
            retrieved = await self.knowledge.retrieve(question)
            metrics.record_ai_event("ai_retrieval")
            if not retrieved:
                answer = "I couldn't find that in ShopSmart's policy information."
                answerable = False
                reason = "NO_POLICY_EVIDENCE"
            else:
                generated = await self.gateway.answer(
                    question,
                    self.knowledge.evidence(retrieved),
                    DataClassification.PUBLIC,
                )
                answer = generated.answer.answer
                answerable = generated.answer.answerable
                used_ids = set(generated.answer.evidence_ids)
                citations = [
                    Citation(
                        citation_id=f"source-{index + 1}",
                        document_id=item.source_id,
                        knowledge_version_id=item.chunk.version_id,
                        source_label=item.chunk.source_label,
                        page_number=item.chunk.page_number,
                        chunk_index=item.chunk.chunk_index,
                    )
                    for index, item in enumerate(retrieved)
                    if str(item.chunk.id) in used_ids
                ]
        else:
            answer = "I can help with ShopSmart products, offers, your cart or orders, and policy questions."
        if not answerable:
            metrics.record_ai_event("ai_no_answer")

        citation_dicts = [item.model_dump(mode="json") for item in citations]
        await self.conversations.add_message(
            conversation.id, user_id, "user", question, token_count=len(question.split())
        )
        assistant_message = await self.conversations.add_message(
            conversation.id,
            user_id,
            "assistant",
            answer,
            citations=citation_dicts,
            result_data=data,
            token_count=len(answer.split()),
        )
        await self.db.commit()
        return {
            "conversation_id": conversation.id,
            "message_id": assistant_message.id,
            "answer": answer,
            "answerable": answerable,
            "reason": reason,
            "citations": citations,
            "intent": route.intent.value,
            "result_data": data,
        }

    @staticmethod
    def _search_terms(question: str, category: str | None = None) -> list[str]:
        normalized = re.sub(
            r"\b(?:under|below|less than|up to|at most|over|above|more than|greater than|at least)"
            r"\s*\$?\s*\d+(?:\.\d{1,2})?\b",
            " ",
            question.lower(),
        )
        if category:
            aliases = sorted(
                (alias for alias, canonical in CATEGORY_ALIASES.items() if canonical == category),
                key=len,
                reverse=True,
            )
            for alias in aliases:
                normalized = re.sub(rf"(?<!\w){re.escape(alias)}(?!\w)", " ", normalized)
        return [
            term
            for term in re.findall(r"[a-z0-9-]+", normalized)
            if term not in _STOP_WORDS and len(term) > 1
        ][:8]

    @staticmethod
    def _product_data(product) -> dict:
        return {
            "id": str(product.id),
            "name": product.name,
            "description": product.description,
            "category": getattr(product, "category", None),
            "sku": product.sku,
            "price_cents": product.price,
            "stock_quantity": product.stock_quantity,
            "max_purchase_quantity": product.max_purchase_quantity,
        }

    @staticmethod
    def _cart_data(cart: dict) -> dict:
        return {
            **cart,
            "items": [{**item, "product_id": str(item["product_id"])} for item in cart["items"]],
        }

    async def _context_products(self, context: dict | None) -> list:
        return await self._products_for_context_key(context, "product_ids")

    async def _products_for_context_key(self, context: dict | None, key: str) -> list:
        ids = (context or {}).get(key, [])
        products = []
        for product_id in ids[:20]:
            try:
                product = await self.catalog.get_product(UUID(product_id))
            except (ValueError, TypeError):
                continue
            if product and product.is_active:
                products.append(product)
        return products

    @staticmethod
    def _asks_for_cheapest(question: str) -> bool:
        return bool(
            re.search(r"\b(?:cheaper|cheapest|less expensive|lower[- ]priced)\b", question, re.I)
        )

    @staticmethod
    def _format_price(price_cents: int) -> str:
        return f"${price_cents / 100:,.2f}"

    @staticmethod
    def _select_comparison_products(question: str, products: list) -> list:
        normalized = question.lower()
        ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}
        indexes = [
            index for word, index in ordinals.items() if re.search(rf"\b{word}\b", normalized)
        ]
        if "first two" in normalized:
            indexes = [0, 1]
        if indexes:
            return [products[index] for index in dict.fromkeys(indexes) if index < len(products)]
        named = [
            product
            for product in products
            if re.search(rf"(?<!\w){re.escape(product.name.lower())}(?!\w)", normalized)
        ]
        return named if named else products[:2]

    async def _resolve_product(self, question: str, context: dict | None):
        context = context or {}
        reference_key = (
            "comparison_product_ids" if context.get("comparison_product_ids") else "product_ids"
        )
        products = await self._products_for_context_key(context, reference_key)
        if not products:
            return None
        normalized = question.lower()
        if self._asks_for_cheapest(question):
            cheapest = min(products, key=lambda item: item.price)
            if sum(item.price == cheapest.price for item in products) > 1:
                return None
            return cheapest
        for index, product in enumerate(products):
            if product.name.lower() in normalized:
                return product
            ordinal = ("first", "second", "third", "fourth", "fifth")
            if index < len(ordinal) and ordinal[index] in normalized:
                return product
        if re.search(r"\bthat\s+(?:one|product)\b|\bit\b", normalized):
            selected_id = context.get("selected_product_id")
            if selected_id:
                for product in products:
                    if str(product.id) == selected_id:
                        return product
        if len(products) == 1 and any(word in normalized for word in ("this", "that", "it")):
            return products[0]
        return None

    @staticmethod
    def _cart_summary(cart: dict) -> str:
        count = sum(item["quantity"] for item in cart["items"])
        if not count:
            return "Your cart is empty."
        subtotal = cart["subtotal"] / 100
        return f"Your cart has {count} item(s), with a subtotal of ${subtotal:,.2f}."
