"""Schema verification for the products Alembic revision."""

from importlib import import_module

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, create_engine, inspect

from src.models.product import Product

product_migration = import_module("migrations.versions.003_create_products_table")


def test_product_migration_matches_model_columns_constraints_and_indexes():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                product_migration.upgrade()

            inspector = inspect(connection)
            migrated_columns = {column["name"] for column in inspector.get_columns("products")}
            model_columns = {column.name for column in Product.__table__.columns}
            assert migrated_columns == model_columns

            migrated_checks = {
                constraint["name"]
                for constraint in inspector.get_check_constraints("products")
            }
            model_checks = {
                constraint.name
                for constraint in Product.__table__.constraints
                if isinstance(constraint, CheckConstraint)
            }
            assert migrated_checks == model_checks

            migrated_indexes = {
                index["name"]: index["unique"]
                for index in inspector.get_indexes("products")
            }
            model_indexes = {
                index.name: index.unique for index in Product.__table__.indexes
            }
            assert migrated_indexes == model_indexes

            with Operations.context(MigrationContext.configure(connection)):
                product_migration.downgrade()
            assert "products" not in inspect(connection).get_table_names()
    finally:
        engine.dispose()
