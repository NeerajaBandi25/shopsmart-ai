from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.core import session_validator as session_validator_module
from src.core.observability import request_id_context


@pytest.mark.parametrize(
    ("failure", "event"),
    [
        (
            SQLAlchemyError("database details contain sensitive material"),
            "session_validation_database_error",
        ),
        (
            RuntimeError("unexpected details contain sensitive material"),
            "session_validation_unexpected_error",
        ),
    ],
)
@pytest.mark.asyncio
async def test_validation_failures_are_logged_safely_and_fail_closed(
    failure, event, caplog, monkeypatch
):
    db = AsyncMock()
    db.execute.side_effect = failure
    logger = session_validator_module._logger
    # Alembic's fileConfig disables existing module loggers during the full suite.
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logger, "propagate", True)
    token = request_id_context.set("req-safe-test-123")
    try:
        with caplog.at_level("ERROR", logger="shopsmart.session"):
            result = await session_validator_module.validate_session(
                "3dfac6e7-e495-4e17-9a5a-3eff0e404a93", db
            )
    finally:
        request_id_context.reset(token)

    assert result is None
    db.rollback.assert_awaited_once()
    record = next(record for record in caplog.records if record.name == "shopsmart.session")
    assert record.event == event
    assert record.request_id == "req-safe-test-123"
    assert record.exception_type == type(failure).__name__
    assert "3dfac6e7" not in caplog.text
    assert "sensitive material" not in caplog.text
