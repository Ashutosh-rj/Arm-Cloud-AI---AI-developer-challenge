import os
import logging
from typing import Optional
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None

async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        logger.info(f"Redis client connected to {redis_url}")
    return _redis

async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")

async def health_check() -> bool:
    try:
        redis = await get_redis()
        await redis.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False
