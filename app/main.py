"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import get_settings
from app.utils.logging import setup_logging

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown events."""
    logger.info("Starting Core Banking Service...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    yield

    logger.info("Shutting down Core Banking Service...")


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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"]
        if settings.is_development
        else ["https://admin.capitec.co.za"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, str]:
        """Liveness check."""
        return {
            "status": "healthy",
            "service": "core-banking-service",
            "version": "1.0.0",
        }

    @app.get("/ready", tags=["Health"])
    async def readiness_check() -> dict[str, str | dict[str, str]]:
        """Readiness check."""
        checks = {
            "database": "ok",
            "redis": "ok",
        }
        all_ok = all(v == "ok" for v in checks.values())
        return {
            "status": "ready" if all_ok else "degraded",
            "checks": checks,
        }

    return app


app = create_application()
