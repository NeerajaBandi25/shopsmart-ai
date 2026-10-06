import json
import logging

from src.core.observability import JsonLogFormatter
from src.services.payment_reservation_worker import safe_worker_error_context


class DatabaseError(Exception):
    sqlstate = "42501"


def test_worker_error_context_classifies_and_redacts_database_error():
    error = RuntimeError("database operation failed")
    error.orig = DatabaseError(
        "permission denied connecting to postgresql://alice:secret@localhost/db "
        "password=supersecret"
    )

    context = safe_worker_error_context(error)

    assert context["error_category"] == "insufficient_privilege"
    assert "secret" not in context["error_message"]
    assert "[redacted]" in context["error_message"]


def test_worker_error_context_identifies_missing_relation_and_caps_message():
    class UndefinedTableError(Exception):
        sqlstate = "42P01"

    error = RuntimeError("database operation failed")
    error.orig = UndefinedTableError("x" * 400)

    context = safe_worker_error_context(error)

    assert context["error_category"] == "undefined_table"
    assert len(context["error_message"]) == 240


def test_structured_formatter_includes_worker_error_context():
    record = logging.LogRecord("worker", logging.ERROR, "", 0, "sweep_failed", (), None)
    record.error_category = "database_error"
    record.error_message = "connection refused"

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["context"]["error_category"] == "database_error"
    assert payload["context"]["error_message"] == "connection refused"
