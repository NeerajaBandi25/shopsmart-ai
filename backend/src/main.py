"""FastAPI application initialization."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.api.v1 import auth_routes, product_routes, user_routes
from src.core.config import settings
from src.core.exceptions import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
)
from src.core.observability import (
    RequestObservabilityMiddleware,
    configure_structured_logging,
    security_audit_event,
)
from src.database import close_db, engine, init_db
from src.middleware.session_refresh import SessionRefreshMiddleware

logger = logging.getLogger(__name__)
configure_structured_logging(settings.log_level)


# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    logger.info("Starting up application...")
    if settings.auto_create_tables:
        await init_db()
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Authentication and account foundation for ShopSmart AI",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Add session refresh middleware
app.add_middleware(SessionRefreshMiddleware)
app.add_middleware(RequestObservabilityMiddleware)


# Exception handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle application exceptions."""
    if isinstance(exc, AuthenticationError) and request.url.path != "/api/v1/auth/login":
        security_audit_event(
            "authentication_failure",
            success=False,
            user_id=getattr(request.state, "user_id", None),
            client_ip=request.client.host if request.client else None,
            reason=exc.error_code,
        )
    elif isinstance(exc, AuthorizationError):
        security_audit_event(
            "authorization_denied",
            success=False,
            user_id=getattr(request.state, "user_id", None),
            client_ip=request.client.host if request.client else None,
            reason=exc.error_code,
        )

    response_headers = {}
    if isinstance(exc, RateLimitError):
        response_headers.update(exc.rate_limit_headers)
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response_headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=exc.status_code,
        headers=response_headers,
        content={
            "detail": exc.message,
            "status_code": exc.status_code,
            "error_code": exc.error_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions (never expose stack traces)."""
    logger.error(
        "unhandled_exception",
        extra={"event": "unhandled_exception", "exception_type": type(exc).__name__},
    )
    response_headers = {}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=500,
        headers=response_headers,
        content={
            "detail": "Internal server error",
            "status_code": 500,
            "error_code": "INTERNAL_ERROR",
        },
    )


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/readiness", tags=["Health"])
async def readiness_check():
    """Readiness check endpoint."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Service unavailable",
                "status_code": 503,
                "error_code": "DATABASE_UNAVAILABLE",
            },
        )
    return {"status": "ready"}


# Include API routes
app.include_router(auth_routes.router, prefix="/api/v1")
app.include_router(product_routes.router, prefix="/api/v1")
app.include_router(user_routes.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
