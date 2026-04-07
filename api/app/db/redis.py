import os
import json
from redis.asyncio import Redis
from app.logger import get_logger

logger = get_logger(__name__)

class RedisClient:
    def __init__(self):
        self.redis = Redis.from_url(os.environ["REDIS_URI"])

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

    async def delete(self, key: str):
        await self.redis.delete(key)

    async def close(self):
        await self.redis.aclose()