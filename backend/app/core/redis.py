"""
Redis connection pool for caching and rate-limit counters.

v1: Redis is used ONLY for cache + rate-limit, NOT as a task broker.
See Architecture Section 1.2 (no Celery in v1).
"""
import redis.asyncio as redis

from app.core.config import settings

redis_pool: redis.Redis | None = None


async def init_redis() -> redis.Redis:
    """Initialize Redis connection pool. Called during app lifespan startup."""
    global redis_pool
    redis_pool = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    return redis_pool


async def close_redis() -> None:
    """Close Redis connection pool. Called during app lifespan shutdown."""
    global redis_pool
    if redis_pool:
        await redis_pool.aclose()
        redis_pool = None


def get_redis() -> redis.Redis:
    """
    Dependency to inject Redis into route handlers.

    Usage: r: redis.Redis = Depends(get_redis)
    """
    if redis_pool is None:
        raise RuntimeError("Redis not initialized. Call init_redis() during startup.")
    return redis_pool
