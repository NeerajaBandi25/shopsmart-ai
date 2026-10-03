"""Seed/reset a deterministic synthetic ShopSmart validation dataset locally."""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, or_, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from src.core.security import hash_password
from src.models.ai import (
    ChatMessage,
    Conversation,
    Document,
    DocumentChunk,
    DocumentVersion,
    KnowledgeChunk,
    KnowledgeSource,
    KnowledgeVersion,
)
from src.models.cart import Cart, CartItem
from src.models.login_attempt import LoginAttempt
from src.models.order import Order, OrderItem
from src.models.product import Product
from src.models.session import Session
from src.models.user import User

DATASET_PATH = Path(__file__).with_name("production_like_v1.json")
DATASET_VERSION = "production-like-v1"
SKU_PREFIX = "SYNTH-EVAL-V1-"
EMAIL_SUFFIX = "@shopsmart.local.invalid"
KNOWLEDGE_PREFIX = "local-eval-v1-"
ALLOWED_LOCAL_ENVS = {"local", "dev", "development", "test"}
PRODUCTION_ENVS = {"prod", "production", "staging", "stage"}


class SeedSafetyError(ValueError):
    """The requested seed operation is not safe for this target."""


class SeedOwnershipConflictError(ValueError):
    """A reserved deterministic seed identity belongs to unexpected data."""


SeedOwnershipConflict = SeedOwnershipConflictError


def load_manifest() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def stable_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"shopsmart/{DATASET_VERSION}/{kind}/{key}")


def build_products(manifest: dict | None = None) -> list[Product]:
    manifest = manifest or load_manifest()
    categories = manifest["categories"]
    brands = manifest["brands"]
    products = []
    for index in range(manifest["product_count"]):
        category = categories[index % len(categories)]
        sku = f"{SKU_PREFIX}{index + 1:05d}"
        digest = hashlib.sha256(f"{manifest['version']}:{index}:price".encode()).digest()
        price_range = category["max_price_cents"] - category["min_price_cents"] + 1
        price = category["min_price_cents"] + int.from_bytes(digest[:4], "big") % price_range
        stock_slot = index % 17
        stock = 0 if stock_slot == 0 else 1 + index % 3 if stock_slot <= 3 else 5 + index % 46
        description_index = index % len(category["descriptions"])
        name = f"{brands[index % len(brands)]} {category['label']} Model {index + 1:04d}"
        description = (
            f"Synthetic {category['key']} product. {category['descriptions'][description_index]}; "
            f"browse {category['search_term']} in the local validation catalog."
        )
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(
            days=index % 365, seconds=(index * 37) % 86400
        )
        products.append(
            Product(
                id=stable_id("product", sku),
                name=name,
                description=description,
                category=category["key"],
                sku=sku,
                price=price,
                stock_quantity=stock,
                max_purchase_quantity=5,
                is_active=index % 41 != 0,
                created_at=created_at,
                updated_at=created_at,
            )
        )
    return products


def user_id(user_key: str) -> UUID:
    return stable_id("user", user_key)


def _request_hash(items: list[tuple[UUID, int]]) -> str:
    canonical = sorted((str(product_id), quantity) for product_id, quantity in items)
    encoded = json.dumps(canonical, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_target(
    action: str,
    apply: bool,
    confirmation: str | None,
    environment: dict[str, str],
    database_url: str,
) -> None:
    if action not in {"seed", "reset-seeded-data"}:
        raise SeedSafetyError("Unknown seed operation.")
    if not apply or environment.get("SHOPSMART_ALLOW_DEMO_SEEDING") != "true":
        raise SeedSafetyError("Pass --apply and set SHOPSMART_ALLOW_DEMO_SEEDING=true.")
    if action == "reset-seeded-data" and confirmation != DATASET_VERSION:
        raise SeedSafetyError(f"Reset requires --confirm-version {DATASET_VERSION}.")
    for variable in ("APP_ENV", "ENVIRONMENT", "NODE_ENV"):
        if environment.get(variable, "").strip().lower() in PRODUCTION_ENVS:
            raise SeedSafetyError("Seed operations are forbidden in production-like environments.")
    if environment.get("SHOPSMART_ENV", "").strip().lower() not in ALLOWED_LOCAL_ENVS:
        raise SeedSafetyError("Set SHOPSMART_ENV to local, development, or test.")
    try:
        database = make_url(database_url)
    except Exception as error:
        raise SeedSafetyError("The database target is invalid.") from error
    loopback_hosts = {"localhost", "127.0.0.1", "::1"}
    query_host = database.query.get("host")
    explicit_hosts = [host for host in (database.host, query_host) if host]
    explicit_loopback = bool(explicit_hosts) and all(
        host in loopback_hosts for host in explicit_hosts
    )
    default_socket = (
        not explicit_hosts
        and environment.get("PGHOST") in {None, "", "localhost", "127.0.0.1", "::1"}
        and not environment.get("PGHOSTADDR")
        and not environment.get("PGSERVICE")
        and not database.query.get("service")
    )
    if not explicit_loopback and not default_socket:
        raise SeedSafetyError("Seed operations require a loopback database host.")
    if database.database and any(
        part in database.database.lower().replace("_", "-").split("-")
        for part in ("prod", "production", "stage", "staging")
    ):
        raise SeedSafetyError("Seed operations are forbidden for production-like databases.")
    if action == "seed" and not environment.get("SHOPSMART_LOCAL_SEED_PASSWORD"):
        raise SeedSafetyError("Set SHOPSMART_LOCAL_SEED_PASSWORD for the synthetic local accounts.")


def _user_specs(manifest: dict) -> list[dict]:
    return manifest["users"]


async def _validate_reserved_identities(session: AsyncSession, manifest: dict) -> None:
    products = build_products(manifest)
    product_ids = {item.id: item.sku for item in products}
    product_skus = {item.sku: item.id for item in products}
    by_product_id = (
        (await session.execute(select(Product).where(Product.id.in_(product_ids)))).scalars().all()
    )
    by_product_sku = (
        (await session.execute(select(Product).where(Product.sku.in_(product_skus))))
        .scalars()
        .all()
    )
    for item in by_product_id:
        if item.sku != product_ids[item.id]:
            raise SeedOwnershipConflictError(
                "A deterministic product ID belongs to an unexpected SKU."
            )
    for item in by_product_sku:
        if item.id != product_skus[item.sku]:
            raise SeedOwnershipConflictError(
                "A reserved validation SKU belongs to another product."
            )

    users = _user_specs(manifest)
    expected_users = {user_id(spec["key"]): spec["email"] for spec in users}
    expected_emails = {email: identifier for identifier, email in expected_users.items()}
    by_user_id = (
        (await session.execute(select(User).where(User.id.in_(expected_users)))).scalars().all()
    )
    by_user_email = (
        (await session.execute(select(User).where(User.email.in_(expected_emails)))).scalars().all()
    )
    for user in by_user_id:
        if user.email != expected_users[user.id]:
            raise SeedOwnershipConflictError(
                "A deterministic account ID belongs to an unexpected email."
            )
    for user in by_user_email:
        if user.id != expected_emails[user.email]:
            raise SeedOwnershipConflictError(
                "A reserved synthetic email belongs to another account."
            )


async def seed_dataset(session: AsyncSession, password: str) -> dict[str, int]:
    """Insert/update only identities within the production-like-v1 namespace."""
    manifest = load_manifest()
    await _validate_reserved_identities(session, manifest)

    generated_products = build_products(manifest)
    product_ids = [item.id for item in generated_products]
    existing_products = (
        (await session.execute(select(Product).where(Product.id.in_(product_ids)))).scalars().all()
    )
    existing_by_id = {item.id: item for item in existing_products}
    for generated in generated_products:
        existing = existing_by_id.get(generated.id)
        if existing is None:
            session.add(generated)
            continue
        for field in (
            "name",
            "description",
            "category",
            "sku",
            "price",
            "stock_quantity",
            "max_purchase_quantity",
            "is_active",
            "created_at",
            "updated_at",
        ):
            setattr(existing, field, getattr(generated, field))
    await session.flush()
    product_by_sku = {item.sku: item for item in generated_products}

    user_specs = _user_specs(manifest)
    expected_user_ids = [user_id(spec["key"]) for spec in user_specs]
    existing_users = (
        (await session.execute(select(User).where(User.id.in_(expected_user_ids)))).scalars().all()
    )
    user_by_id = {item.id: item for item in existing_users}
    for spec in user_specs:
        identifier = user_id(spec["key"])
        if identifier not in user_by_id:
            session.add(
                User(id=identifier, email=spec["email"], password_hash=hash_password(password))
            )
    await session.flush()

    cart_specs = []
    for spec in user_specs:
        cart_identifier = stable_id("cart", spec["key"])
        cart_specs.append((spec, cart_identifier))
    existing_carts = (
        (
            await session.execute(
                select(Cart).where(
                    or_(
                        Cart.id.in_([identifier for _, identifier in cart_specs]),
                        Cart.user_id.in_(expected_user_ids),
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    carts_by_id = {item.id: item for item in existing_carts}
    for spec, identifier in cart_specs:
        owner_id = user_id(spec["key"])
        existing_by_owner = next(
            (item for item in existing_carts if item.user_id == owner_id), None
        )
        if existing_by_owner and existing_by_owner.id != identifier:
            raise SeedOwnershipConflictError(
                "A synthetic account has a cart outside the seed namespace."
            )
        if identifier in carts_by_id and carts_by_id[identifier].user_id != owner_id:
            raise SeedOwnershipConflictError("A deterministic cart ID belongs to another account.")
        if identifier not in carts_by_id:
            session.add(Cart(id=identifier, user_id=owner_id))
    await session.flush()
    owned_cart_ids = [identifier for _, identifier in cart_specs]
    await session.execute(delete(CartItem).where(CartItem.cart_id.in_(owned_cart_ids)))
    cart_items = []
    for spec, cart_identifier in cart_specs:
        for item_index, line in enumerate(spec["cart"]):
            product = product_by_sku[line["sku"]]
            cart_items.append(
                CartItem(
                    id=stable_id("cart-item", f"{spec['key']}:{item_index}:{line['sku']}"),
                    cart_id=cart_identifier,
                    product_id=product.id,
                    quantity=line["quantity"],
                )
            )
    session.add_all(cart_items)

    order_specs = []
    for spec in user_specs:
        for order_index, order_spec in enumerate(spec["orders"]):
            order_key = f"{spec['key']}:{order_index}"
            order_specs.append((spec, order_spec, order_key, stable_id("order", order_key)))
    order_ids = [entry[3] for entry in order_specs]
    order_keys = [f"seed:{DATASET_VERSION}:{entry[2]}" for entry in order_specs]
    existing_orders = (
        (
            await session.execute(
                select(Order)
                .options(selectinload(Order.items))
                .where(or_(Order.id.in_(order_ids), Order.idempotency_key.in_(order_keys)))
            )
        )
        .scalars()
        .all()
        if order_ids
        else []
    )
    orders_by_id = {item.id: item for item in existing_orders}
    orders_by_key = {item.idempotency_key: item for item in existing_orders}
    for spec, order_spec, order_key, identifier in order_specs:
        key = f"seed:{DATASET_VERSION}:{order_key}"
        expected_owner = user_id(spec["key"])
        existing = orders_by_id.get(identifier) or orders_by_key.get(key)
        if existing and (
            existing.id != identifier
            or existing.user_id != expected_owner
            or existing.idempotency_key != key
        ):
            raise SeedOwnershipConflictError(
                "A deterministic order marker belongs to unexpected data."
            )
        order_items = []
        for item_index, line in enumerate(order_spec["items"]):
            product = product_by_sku[line["sku"]]
            line_total = product.price * line["quantity"]
            order_items.append(
                OrderItem(
                    id=stable_id("order-item", f"{order_key}:{item_index}"),
                    product_id=product.id,
                    product_name=product.name,
                    product_sku=product.sku,
                    unit_price_cents=product.price,
                    quantity=line["quantity"],
                    line_total_cents=line_total,
                )
            )
        total = sum(item.line_total_cents for item in order_items)
        created_at = datetime(2025, 12, 1, tzinfo=timezone.utc) - timedelta(
            days=int(order_key.rsplit(":", 1)[1])
        )
        if existing is None:
            session.add(
                Order(
                    id=identifier,
                    user_id=expected_owner,
                    idempotency_key=key,
                    request_hash=_request_hash(
                        [
                            (product_by_sku[line["sku"]].id, line["quantity"])
                            for line in order_spec["items"]
                        ]
                    ),
                    status=order_spec["status"],
                    total_cents=total,
                    items=order_items,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
        else:
            existing.items.clear()
            existing.status = order_spec["status"]
            existing.total_cents = total
            existing.request_hash = _request_hash(
                [(product_by_sku[line["sku"]].id, line["quantity"]) for line in order_spec["items"]]
            )
            existing.created_at = created_at
            existing.updated_at = created_at
            existing.items.extend(order_items)

    await session.flush()
    await session.commit()

    from src.services.assistant_knowledge import KnowledgeIngestionService

    ingestion = KnowledgeIngestionService(session)
    for source in manifest["knowledge"]:
        await ingestion.publish(
            source_key=source["source_key"],
            title=source["title"],
            category=source["category"],
            content=source["content"],
        )
    out_of_stock = sum(item.stock_quantity == 0 and item.is_active for item in generated_products)
    return {
        "products": len(generated_products),
        "users": len(user_specs),
        "carts": len(cart_specs),
        "cart_items": len(cart_items),
        "orders": len(order_specs),
        "knowledge_sources": len(manifest["knowledge"]),
        "active_out_of_stock_products": out_of_stock,
    }


async def reset_seeded_data(session: AsyncSession) -> dict[str, int]:
    """Remove only production-like-v1 identities; preserve unrelated references/data."""
    manifest = load_manifest()
    products = build_products(manifest)
    product_by_id = {item.id: item for item in products}
    product_ids = list(product_by_id)
    users = _user_specs(manifest)
    owned_user_ids = [user_id(spec["key"]) for spec in users]
    owned_emails = [spec["email"] for spec in users]
    cart_ids = [stable_id("cart", spec["key"]) for spec in users]
    order_markers = {
        stable_id("order", f"{spec['key']}:{index}"): (
            user_id(spec["key"]),
            f"seed:{DATASET_VERSION}:{spec['key']}:{index}",
        )
        for spec in users
        for index, _ in enumerate(spec["orders"])
    }
    order_keys = [marker[1] for marker in order_markers.values()]

    await _validate_reserved_identities(session, manifest)
    cart_owners = {stable_id("cart", spec["key"]): user_id(spec["key"]) for spec in users}
    existing_carts = (
        (
            await session.execute(
                select(Cart).where(
                    or_(
                        Cart.id.in_(cart_ids),
                        Cart.user_id.in_(owned_user_ids),
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    if any(cart_owners.get(cart.id) != cart.user_id for cart in existing_carts):
        raise SeedOwnershipConflictError("A reserved cart identity belongs to unexpected data.")

    external_cart_reference = await session.scalar(
        select(CartItem.id)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(CartItem.product_id.in_(product_ids), Cart.user_id.not_in(owned_user_ids))
        .limit(1)
    )
    external_order_reference = await session.scalar(
        select(OrderItem.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.product_id.in_(product_ids), Order.id.not_in(list(order_markers)))
        .limit(1)
    )
    if external_cart_reference or external_order_reference:
        raise SeedOwnershipConflictError(
            "A non-seeded shopper references a seeded product; reset refused without changes."
        )

    source_keys = [source["source_key"] for source in manifest["knowledge"]]
    sources = (
        (
            await session.execute(
                select(KnowledgeSource).where(KnowledgeSource.source_key.in_(source_keys))
            )
        )
        .scalars()
        .all()
    )
    source_ids = [source.id for source in sources]
    if source_ids:
        await session.execute(
            update(KnowledgeSource)
            .where(KnowledgeSource.id.in_(source_ids))
            .values(active_version_id=None)
        )
        await session.flush()
        version_ids = (
            (
                await session.execute(
                    select(KnowledgeVersion.id).where(KnowledgeVersion.source_id.in_(source_ids))
                )
            )
            .scalars()
            .all()
        )
        if version_ids:
            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.version_id.in_(version_ids))
            )
            await session.execute(
                delete(KnowledgeVersion).where(KnowledgeVersion.id.in_(version_ids))
            )
        await session.execute(delete(KnowledgeSource).where(KnowledgeSource.id.in_(source_ids)))

    owned_orders = (
        (
            await session.execute(
                select(Order).where(
                    or_(Order.id.in_(list(order_markers)), Order.idempotency_key.in_(order_keys))
                )
            )
        )
        .scalars()
        .all()
    )
    for order in owned_orders:
        marker = order_markers.get(order.id)
        if marker is None or order.user_id != marker[0] or order.idempotency_key != marker[1]:
            raise SeedOwnershipConflictError("An order marker belongs to unexpected data.")
    order_ids = [order.id for order in owned_orders]
    if order_ids:
        await session.execute(delete(OrderItem).where(OrderItem.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.id.in_(order_ids)))

    await session.execute(delete(CartItem).where(CartItem.cart_id.in_(cart_ids)))
    await session.execute(
        delete(Cart).where(Cart.id.in_(cart_ids), Cart.user_id.in_(owned_user_ids))
    )

    conversation_ids = (
        (
            await session.execute(
                select(Conversation.id).where(Conversation.owner_id.in_(owned_user_ids))
            )
        )
        .scalars()
        .all()
    )
    if conversation_ids:
        await session.execute(
            delete(ChatMessage).where(ChatMessage.conversation_id.in_(conversation_ids))
        )
        await session.execute(delete(Conversation).where(Conversation.id.in_(conversation_ids)))
    document_ids = (
        (await session.execute(select(Document.id).where(Document.owner_id.in_(owned_user_ids))))
        .scalars()
        .all()
    )
    if document_ids:
        await session.execute(
            update(Document).where(Document.id.in_(document_ids)).values(active_version_id=None)
        )
        await session.flush()
        version_ids = (
            (
                await session.execute(
                    select(DocumentVersion.id).where(DocumentVersion.document_id.in_(document_ids))
                )
            )
            .scalars()
            .all()
        )
        if version_ids:
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id.in_(document_ids))
            )
            await session.execute(
                delete(DocumentVersion).where(DocumentVersion.id.in_(version_ids))
            )
        await session.execute(delete(Document).where(Document.id.in_(document_ids)))
    await session.execute(delete(Session).where(Session.user_id.in_(owned_user_ids)))
    await session.execute(delete(LoginAttempt).where(LoginAttempt.email.in_(owned_emails)))

    await session.execute(delete(Product).where(Product.id.in_(product_ids)))
    await session.execute(delete(User).where(User.id.in_(owned_user_ids)))
    await session.commit()
    return {
        "products": len(product_ids),
        "users": len(owned_user_ids),
        "carts": len(cart_ids),
        "orders": len(order_ids),
        "knowledge_sources": len(source_ids),
    }


async def run_operation(
    action: str,
    *,
    apply: bool,
    confirmation: str | None,
    environment: dict[str, str],
    database_url: str,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    try:
        validate_target(action, apply, confirmation, environment, database_url)
        if session_factory is None:
            from src.database import AsyncSessionLocal

            session_factory = AsyncSessionLocal
        async with session_factory() as session:
            result = (
                await seed_dataset(session, environment["SHOPSMART_LOCAL_SEED_PASSWORD"])
                if action == "seed"
                else await reset_seeded_data(session)
            )
    except SeedSafetyError as error:
        print(f"Production-like data operation refused; no changes made. {error}")
        return 2
    except SeedOwnershipConflictError as error:
        print(f"Production-like data operation refused; no changes made. {error}")
        return 2
    except Exception as error:
        print(
            f"Production-like data operation failed ({type(error).__name__}); "
            "database details and seed content were suppressed.",
            file=sys.stderr,
        )
        return 1
    action_text = "Seeded" if action == "seed" else "Removed"
    counts = ", ".join(f"{key}={value}" for key, value in result.items())
    print(f"{action_text} {DATASET_VERSION}: {counts}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seed", "reset-seeded-data"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-version")
    args = parser.parse_args(argv)
    environment = dict(os.environ)
    try:
        validate_target(
            args.action,
            args.apply,
            args.confirm_version,
            environment,
            "postgresql+asyncpg://local:local@localhost/local",
        )
        from src.core.config import settings

        database_url = settings.database_url
    except SeedSafetyError as error:
        print(f"Production-like data operation refused; no changes made. {error}")
        return 2
    except Exception as error:
        print(
            f"Production-like data operation refused; local configuration is unavailable "
            f"({type(error).__name__}).",
            file=sys.stderr,
        )
        return 2
    return asyncio.run(
        run_operation(
            args.action,
            apply=args.apply,
            confirmation=args.confirm_version,
            environment=environment,
            database_url=database_url,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
