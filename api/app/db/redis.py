import json
import secrets

from redis.asyncio import Redis

from app.logger import get_logger
from app.settings import get_settings

logger = get_logger(__name__)

class RedisClient:
    def __init__(self):
        redis_uri = get_settings().redis_uri
        if not redis_uri:
            raise KeyError("REDIS_URI")
        self.redis = Redis.from_url(redis_uri)

    async def ping(self) -> bool:
        try:
            await self.redis.ping()
            logger.debug("Redis ping successful")
            return True
        except Exception as e:
            logger.error("Redis ping failed: %s", e)
            return False

    async def set(self, key: str, value: str, expire: int = None):
        await self.redis.set(key, json.dumps(value), ex=expire)

    async def get(self, key: str) -> str | None:
        value = await self.redis.get(key)
        if value is not None:
            return json.loads(value)
        return None

    async def incr(self, key: str) -> int:
        return await self.redis.incr(key)

    async def expire(self, key: str, seconds: int):
        await self.redis.expire(key, seconds)

    async def incr_with_expire(self, key: str, window: int) -> int:
        """Atomically increment a counter and set its TTL on first use (Lua script)."""
        script = (
            "local c = redis.call('INCR', KEYS[1]) "
            "if c == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end "
            "return c"
        )
        return await self.redis.eval(script, 1, key, window)

    async def acquire_lock(self, key: str, ttl_seconds: int) -> str | None:
        """Take a lock (SET NX EX). Returns a release token, or None if held."""
        token = secrets.token_hex(16)
        if await self.redis.set(key, token, nx=True, ex=ttl_seconds):
            return token
        return None

    async def release_lock(self, key: str, token: str) -> None:
        """Release a lock only if this token still holds it (Lua compare-and-delete)."""
        script = (
            "if redis.call('GET', KEYS[1]) == ARGV[1] then "
            "return redis.call('DEL', KEYS[1]) end return 0"
        )
        await self.redis.eval(script, 1, key, token)

    async def delete(self, key: str):
        await self.redis.delete(key)

    async def close(self):
        await self.redis.aclose()