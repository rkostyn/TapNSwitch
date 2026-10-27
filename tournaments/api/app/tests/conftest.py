import base64
import os
from datetime import UTC, datetime
from unittest.mock import patch

import bcrypt
import pytest
from fastapi.testclient import TestClient

# Set env vars before importing anything from the app so MongoClient and
# RedisClient constructors don't KeyError on missing MONGODB_URI / REDIS_URI.
os.environ.setdefault("MONGODB_URI", "mongodb://fake-host:27017")
os.environ.setdefault("REDIS_URI", "redis://fake-host:6379/0")

from app.dependencies import get_mongo_client, get_redis_client  # noqa: E402
from app.main import app  # noqa: E402
from app.tests.fakes import FakeMongoClient, FakeRedisClient  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fake instances — single instances used for the entire test session
# ---------------------------------------------------------------------------
_fake_mongo = FakeMongoClient()
_fake_redis = FakeRedisClient()

# Override FastAPI dependency injection so all route handlers receive fakes
app.dependency_overrides[get_mongo_client] = lambda: _fake_mongo
app.dependency_overrides[get_redis_client] = lambda: _fake_redis


def _seed_test_data():
    """Synchronously pre-populate the in-memory stores with test fixtures."""
    password_hash = bcrypt.hashpw(b"testpassword", bcrypt.gensalt()).decode()
    users = _fake_mongo._get_or_create("axes", "users")
    users._docs.append({
        "user_id": "test-user-id-fixed",
        "user_name": "testuser",
        "email": "test-user@yeetbox.net",
        "password_hash": password_hash,
        "created_at": datetime.now(UTC),
        "is_admin": False,
    })
    tokens = _fake_mongo._get_or_create("axes", "registration_tokens")
    # One token for test_register to consume
    tokens._docs.append({"token": "test-reg-token"})


_seed_test_data()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client():
    """
    HTTP test client with the app lifespan patched so the startup code
    (index creation, health pings) uses fakes instead of real connections.
    """
    with (
        patch("app.main.MongoClient", return_value=_fake_mongo),
        patch("app.main.RedisClient", return_value=_fake_redis),
    ):
        with TestClient(app) as c:
            yield c


@pytest.fixture
async def mongo_client():
    """Returns the shared FakeMongoClient so tests can inspect/mutate state."""
    return _fake_mongo


@pytest.fixture
async def redis_client():
    """Returns the shared FakeRedisClient."""
    return _fake_redis


@pytest.fixture(scope="session")
def auth_token(client):
    """Obtain a bearer token for 'testuser' (pre-seeded in _seed_test_data)."""
    credentials = base64.b64encode(b"testuser:testpassword").decode()
    response = client.post("/auth/login", json={"credentials": credentials})
    assert response.status_code == 200, f"auth_token login failed: {response.text}"
    return response.json()["access_token"]
