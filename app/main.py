"""FastAPI application entry point."""

import uuid as _uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.config import get_settings
from app.dependencies import create_engine, create_redis, create_session_factory
from app.grpc.fraud_client import FraudEvaluationClient
from app.services.kafka_producer import create_kafka_producer
from app.utils.logging import get_logger, setup_logging

settings = get_settings()
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter (shared instance used by routers via app.state.limiter)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager — owns all shared resources."""
    # Startup
    logger.info("Starting Core Banking Service...")
    logger.info("Environment: %s", settings.environment)
    logger.info("Debug mode: %s", settings.debug)

    engine = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = create_redis(settings)

    # gRPC fraud client (owned by app, not a module-level singleton)
    app.state.fraud_client = FraudEvaluationClient(target=settings.fraud_grpc_target)

    # Kafka producer (best-effort — service works without Kafka)
    try:
        app.state.kafka_producer = await create_kafka_producer(settings)
    except Exception:
        logger.warning("Kafka producer failed to start — transactions won't be published")
        app.state.kafka_producer = None

    yield

    # Shutdown — dispose every resource we created
    logger.info("Shutting down Core Banking Service...")
    if app.state.kafka_producer is not None:
        try:
            await app.state.kafka_producer.stop()
        except Exception:
            logger.warning("Failed to close Kafka producer", exc_info=True)
    try:
        await app.state.fraud_client.close()
    except Exception:
        logger.warning("Failed to close gRPC client", exc_info=True)
    await app.state.redis.aclose()
    await engine.dispose()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# Request ID middleware — inject X-Request-ID for distributed tracing
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID into every request/response cycle."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


# ---------------------------------------------------------------------------
# Global exception handler — never leak internals
# ---------------------------------------------------------------------------


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IntegrityError)
    async def _integrity_error_handler(request: Request, exc: IntegrityError):
        request_id = getattr(request.state, "request_id", "n/a")
        logger.warning(
            "Integrity constraint violation on %s %s (request_id=%s): %s",
            request.method,
            request.url.path,
            request_id,
            exc.orig,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "A record with this identifier already exists"},
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "n/a")
        logger.exception(
            "Unhandled exception on %s %s (request_id=%s)",
            request.method,
            request.url.path,
            request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_application() -> FastAPI:
    """Application factory."""
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Core Banking Service API",
        description="Central platform service for customer identity, accounts, and transactions.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Request ID and security headers (outermost = runs first)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"]
        if settings.is_development
        else ["https://admin.capitec.co.za"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # Exception handlers
    _register_exception_handlers(app)

    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    # ------------------------------------------------------------------
    # Health check endpoints (no prefix)
    # ------------------------------------------------------------------

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, str]:
        """Liveness check — is the process running?"""
        return {
            "status": "healthy",
            "service": "core-banking-service",
            "version": "1.0.0",
        }

    @app.get("/ready", tags=["Health"])
    async def readiness_check(request: Request):
        """Readiness check — can the service handle traffic?"""
        checks: dict[str, str] = {}

        # Database
        try:
            async with request.app.state.session_factory() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "unavailable"

        # Redis
        try:
            await request.app.state.redis.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"

        all_ok = all(v == "ok" for v in checks.values())
        payload = {
            "status": "ready" if all_ok else "degraded",
            "checks": checks,
        }

        if not all_ok:
            return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)
        return payload

    return app


# Create the application instance
app = create_application()
