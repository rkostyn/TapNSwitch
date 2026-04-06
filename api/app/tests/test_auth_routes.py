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
    assert data["expires_in"] == 3600


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
