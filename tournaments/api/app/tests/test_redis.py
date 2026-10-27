"""
Unit tests for the RedisClient wrapper (app/db/redis.py).
The underlying redis.asyncio.Redis is mocked so no real connection is needed.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.redis import RedisClient


@pytest.fixture
def redis_wrapper():
    with patch("app.db.redis.Redis") as mock_cls:
        mock_redis = MagicMock()
        mock_cls.from_url.return_value = mock_redis
        client = RedisClient()
        client._mock = mock_redis
        yield client


async def test_ping_success(redis_wrapper):
    redis_wrapper._mock.ping = AsyncMock(return_value=True)
    assert await redis_wrapper.ping() is True
    redis_wrapper._mock.ping.assert_awaited_once()


async def test_ping_failure(redis_wrapper):
    redis_wrapper._mock.ping = AsyncMock(side_effect=Exception("refused"))
    assert await redis_wrapper.ping() is False


async def test_set_json_encodes_value(redis_wrapper):
    redis_wrapper._mock.set = AsyncMock()
    await redis_wrapper.set("k", "hello", expire=30)
    redis_wrapper._mock.set.assert_awaited_once_with("k", json.dumps("hello"), ex=30)


async def test_set_no_expire(redis_wrapper):
    redis_wrapper._mock.set = AsyncMock()
    await redis_wrapper.set("k", {"a": 1})
    redis_wrapper._mock.set.assert_awaited_once_with("k", json.dumps({"a": 1}), ex=None)


async def test_get_json_decodes_value(redis_wrapper):
    redis_wrapper._mock.get = AsyncMock(return_value=json.dumps("world").encode())
    result = await redis_wrapper.get("k")
    assert result == "world"


async def test_get_missing_key_returns_none(redis_wrapper):
    redis_wrapper._mock.get = AsyncMock(return_value=None)
    result = await redis_wrapper.get("missing")
    assert result is None


async def test_incr_delegates(redis_wrapper):
    redis_wrapper._mock.incr = AsyncMock(return_value=5)
    result = await redis_wrapper.incr("counter")
    assert result == 5
    redis_wrapper._mock.incr.assert_awaited_once_with("counter")


async def test_expire_delegates(redis_wrapper):
    redis_wrapper._mock.expire = AsyncMock()
    await redis_wrapper.expire("k", 60)
    redis_wrapper._mock.expire.assert_awaited_once_with("k", 60)


async def test_delete_delegates(redis_wrapper):
    redis_wrapper._mock.delete = AsyncMock()
    await redis_wrapper.delete("k")
    redis_wrapper._mock.delete.assert_awaited_once_with("k")


async def test_close_calls_aclose(redis_wrapper):
    redis_wrapper._mock.aclose = AsyncMock()
    await redis_wrapper.close()
    redis_wrapper._mock.aclose.assert_awaited_once()
