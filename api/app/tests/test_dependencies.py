import asyncio
import hashlib

import pytest

from app.dependencies import create_access_token, get_redis_client
from app.main import app
from app.tests.fakes import FakeRedisClient


@pytest.fixture
def fake_redis():
    return FakeRedisClient()


async def test_create_access_token_returns_string(fake_redis):
    token = await create_access_token("testsubject", redis_client=fake_redis, expires_seconds=60)
    assert isinstance(token, str)
    assert len(token) > 0


async def test_token_stored_as_hash_not_plaintext(fake_redis):
    token = await create_access_token("testsubject", redis_client=fake_redis, expires_seconds=60)

    # Raw token must NOT be stored as-is
    raw = await fake_redis.get(f"auth:token:{token}")
    assert raw is None

    # The SHA-256 hash is the key that holds the subject
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    subject = await fake_redis.get(f"auth:token:{token_hash}")
    assert subject == "testsubject"


async def test_expired_token_returns_401(client):
    short_lived_redis = FakeRedisClient()
    original = app.dependency_overrides.get(get_redis_client)
    app.dependency_overrides[get_redis_client] = lambda: short_lived_redis

    try:
        token = await create_access_token(
            "testsubject", redis_client=short_lived_redis, expires_seconds=1
        )
        await asyncio.sleep(2)
        response = client.get("/auth/user", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_redis_client] = original
        else:
            app.dependency_overrides.pop(get_redis_client, None)
