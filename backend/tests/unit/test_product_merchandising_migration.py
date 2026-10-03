"""Schema verification for additive product merchandising fields."""

from importlib import import_module

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

product_migration = import_module("migrations.versions.003_create_products_table")
merchandising_migration = import_module("migrations.versions.014_product_merchandising")


def test_merchandising_migration_preserves_existing_products():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                product_migration.upgrade()

            connection.execute(
                text(
                    "INSERT INTO products "
                    "(id, name, description, sku, price, stock_quantity, "
                    "max_purchase_quantity, is_active) "
                    "VALUES ('existing-id', 'Existing product', 'Kept as-is', "
                    "'KEEP-001', 5000, 4, 2, 1)"
                )
            )

            with Operations.context(MigrationContext.configure(connection)):
                merchandising_migration.upgrade()

            columns = {column["name"] for column in inspect(connection).get_columns("products")}
            assert {
                "brand",
                "list_price",
                "image_url",
                "image_alt",
                "image_source_url",
                "image_creator",
                "image_license",
                "image_license_url",
                "image_sha256",
                "specifications",
            } <= columns
            row = connection.execute(
                text("SELECT id, sku, price, stock_quantity FROM products WHERE id = 'existing-id'")
            ).one()
            assert tuple(row) == ("existing-id", "KEEP-001", 5000, 4)
    finally:
        engine.dispose()