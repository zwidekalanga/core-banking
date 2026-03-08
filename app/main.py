"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.config import get_settings
from app.grpc.fraud_client import FraudEvaluationClient
from app.infrastructure import create_engine, create_redis, create_session_factory
from app.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
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

    try:
        engine = create_engine(settings)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
    except Exception:
        logger.exception("Failed to initialise database engine")
        raise

    try:
        app.state.redis = create_redis(settings)
    except Exception:
        logger.exception("Failed to initialise Redis client")
        await engine.dispose()
        raise

    # gRPC fraud client (owned by app, not a module-level singleton)
    try:
        app.state.fraud_client = FraudEvaluationClient(target=settings.fraud_grpc_target)
    except Exception:
        logger.exception("Failed to initialise gRPC fraud client")
        await app.state.redis.aclose()
        await engine.dispose()
        raise

    # Kafka producer (best-effort — service works without Kafka)
    try:
        app.state.kafka_producer = await create_kafka_producer(settings)
    except Exception:
        logger.warning("Kafka producer failed to start — transactions won't be published")
        app.state.kafka_producer = None

    yield

    # Shutdown — dispose every resource; ensure all run even if one fails
    logger.info("Shutting down Core Banking Service...")
    try:
        if app.state.kafka_producer is not None:
            await app.state.kafka_producer.stop()
    except Exception:
        logger.exception("Error closing Kafka producer")
    try:
        await app.state.fraud_client.close()
    except Exception:
        logger.exception("Error closing gRPC fraud client")
    try:
        await app.state.redis.aclose()
    except Exception:
        logger.exception("Error closing Redis connection")
    finally:
        await engine.dispose()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# Global exception handler — never leak internals
# ---------------------------------------------------------------------------


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IntegrityError)
    async def _integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
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
    async def _unhandled_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
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
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]  # slowapi typing mismatch
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

    # Include routers
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(health_router)

    add_pagination(app)

    return app


# Create the application instance
app = create_application()
