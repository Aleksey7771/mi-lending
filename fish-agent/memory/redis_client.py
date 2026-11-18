import redis.asyncio as aioredis

from config import settings

_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True, protocol=2)
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None
