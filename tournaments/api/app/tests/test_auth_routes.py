import base64

import pytest

from app.models.auth import LoginRequest, RegisterRequest

# Registration token seeded in conftest._seed_test_data
REG_TOKEN = "test-reg-token"

# Use a distinct username so it never conflicts with the pre-seeded "testuser"
test_register_request = RegisterRequest(
    username="register_test_user",
    password="testpassword123",
    email="register-test@example.com",
    registration_token=REG_TOKEN,
)


def test_register(client):
    response = client.post("/auth/register", json=test_register_request.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_register_request.username
    assert data["email"] == test_register_request.email
    assert "user_id" in data


def test_login(client):
    credentials = f"{test_register_request.username}:{test_register_request.password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    response = client.post("/auth/login", json=LoginRequest(credentials=encoded).model_dump())
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 604800


def test_refresh_token(client):
    credentials = f"{test_register_request.username}:{test_register_request.password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    old_token = client.post("/auth/login", json={"credentials": encoded}).json()["access_token"]

    response = client.post("/auth/refresh", headers={"Authorization": f"Bearer {old_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["expires_in"] == 604800
    new_token = data["access_token"]
    assert new_token != old_token

    # The new token authenticates, and the old one stays valid until expiry
    assert client.get("/auth/user", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200
    assert client.get("/auth/user", headers={"Authorization": f"Bearer {old_token}"}).status_code == 200


def test_refresh_invalid_token(client):
    response = client.post("/auth/refresh", headers={"Authorization": "Bearer bogus-token"})
    assert response.status_code == 401


def test_refresh_unauthenticated(client):
    response = client.post("/auth/refresh")
    assert response.status_code in (401, 403)


def test_login_invalid_credentials(client):
    credentials = f"{test_register_request.username}:wrongpassword"
    encoded = base64.b64encode(credentials.encode()).decode()
    response = client.post("/auth/login", json={"credentials": encoded})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_malformed_base64(client):
    response = client.post("/auth/login", json={"credentials": "not-valid-base64!!!"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid base64 credentials"


def test_login_missing_separator(client):
    encoded = base64.b64encode(b"nocolon").decode()
    response = client.post("/auth/login", json={"credentials": encoded})
    assert response.status_code == 400
    assert response.json()["detail"] == "Credentials must be user:pass"


def test_register_invalid_token(client):
    response = client.post("/auth/register", json={
        "username": "newuser",
        "password": "somepassword123",
        "email": "new@example.com",
        "registration_token": "invalid-token",
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid registration token"


def test_get_authenticated_user(client):
    credentials = base64.b64encode(b"testuser:testpassword").decode()
    token = client.post("/auth/login", json={"credentials": credentials}).json()["access_token"]
    response = client.get("/auth/user", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["user_name"] == "testuser"
    assert data["email"] == "test-user@yeetbox.net"


def test_get_user_unauthenticated(client):
    response = client.get("/auth/user", headers={"Authorization": "Bearer invalidtoken"})
    assert response.status_code == 401


async def test_login_rate_limit(client, redis_client):
    key = "rate_limit:/auth/login:testclient"
    try:
        await redis_client.delete(key)
        for _ in range(10):
            await redis_client.incr(key)
        credentials = base64.b64encode(b"testuser:wrongpassword").decode()
        response = client.post("/auth/login", json={"credentials": credentials})
        assert response.status_code == 429
    finally:
        await redis_client.delete(key)


async def test_register_rate_limit(client, redis_client):
    key = "rate_limit:/auth/register:testclient"
    try:
        await redis_client.delete(key)
        for _ in range(5):
            await redis_client.incr(key)
        response = client.post("/auth/register", json={
            "username": "ratelimituser",
            "password": "somepassword123",
            "email": "rl@example.com",
            "registration_token": "any",
        })
        assert response.status_code == 429
    finally:
        await redis_client.delete(key)


def test_logout(client):
    credentials = base64.b64encode(b"testuser:testpassword").decode()
    token = client.post("/auth/login", json={"credentials": credentials}).json()["access_token"]
    response = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["message"] == "ok"


def test_logout_unauthenticated(client):
    response = client.post("/auth/logout")
    assert response.status_code == 401


def test_logout_invalidates_token(client):
    credentials = base64.b64encode(b"testuser:testpassword").decode()
    token = client.post("/auth/login", json={"credentials": credentials}).json()["access_token"]
    client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    # Token should no longer work for protected endpoints
    response = client.get("/auth/user", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_register_token_not_consumed_on_duplicate_username(client):
    """Fix 1: a failed registration must not burn the token."""
    from app.tests.conftest import _fake_mongo
    tokens = _fake_mongo._get_or_create("axes", "registration_tokens")
    tokens._docs.append({"token": "preserve-test-token"})

    # First attempt fails — username already exists
    client.post("/auth/register", json={
        "username": "testuser",  # pre-seeded, will conflict
        "password": "password1234",
        "email": "unique-preserve@example.com",
        "registration_token": "preserve-test-token",
    })

    # Token must still be present
    assert any(t.get("token") == "preserve-test-token" for t in tokens._docs)

    # Second attempt with a unique username must succeed using the same token
    response = client.post("/auth/register", json={
        "username": "preserve_user",
        "password": "password1234",
        "email": "unique-preserve@example.com",
        "registration_token": "preserve-test-token",
    })
    assert response.status_code == 200
