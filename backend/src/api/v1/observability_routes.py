"""Operator-facing observability endpoints."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException

from src.core.config import settings
from src.core.observability import metrics
from src.schemas.observability import MetricsSnapshot

router = APIRouter(prefix="/observability", tags=["Observability"])


@router.get("/metrics", response_model=MetricsSnapshot, summary="Read process metrics")
def read_metrics(authorization: Annotated[str | None, Header()] = None) -> MetricsSnapshot:
    """Return bounded process metrics only when a dedicated bearer token is configured."""
    expected_token = settings.observability_metrics_token
    if expected_token is None:
        raise HTTPException(status_code=404, detail="Not found")

    scheme, separator, supplied_token = (authorization or "").partition(" ")
    if (
        scheme.lower() != "bearer"
        or not separator
        or not supplied_token
        or not hmac.compare_digest(supplied_token.encode("utf-8"), expected_token.encode("ascii"))
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return MetricsSnapshot.model_validate(metrics.snapshot())
