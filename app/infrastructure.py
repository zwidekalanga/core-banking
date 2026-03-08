"""Shared infrastructure — engine, session factory, Redis, and container."""

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

# ---------------------------------------------------------------------------
# Factory functions — used by lifespan (main.py) and InfrastructureContainer
# ---------------------------------------------------------------------------


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the async database engine."""
    return create_async_engine(
        str(settings.database_url),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        echo=settings.debug,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create session factory bound to *engine*."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def create_redis(settings: Settings) -> "Redis":
    """Create the async Redis client."""
    return Redis.from_url(str(settings.redis_url), decode_responses=True)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Standalone container for non-FastAPI entry-points (ARCH-003)
# ---------------------------------------------------------------------------


@dataclass
class InfrastructureContainer:
    """Holds shared async resources for non-FastAPI entry-points.

    Replaces module-level global singletons with an explicit,
    immutable container that callers create and own.
    """

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis

    @classmethod
    def from_settings(cls, settings: Settings) -> "InfrastructureContainer":
        """Factory that wires up engine, session factory, and Redis."""
        engine = create_engine(settings)
        return cls(
            engine=engine,
            session_factory=create_session_factory(engine),
            redis=create_redis(settings),
        )

    async def close(self) -> None:
        """Dispose of all managed resources."""
        await self.redis.aclose()
        await self.engine.dispose()
