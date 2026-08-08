import pytest

pytestmark = pytest.mark.asyncio


async def test_register_user(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"name": "Nishant", "email": "nishant@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "nishant@example.com"
    assert body["role"] == "user"
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_duplicate_email(client):
    payload = {"name": "Nishant", "email": "dup@example.com", "password": "password123"}
    resp1 = await client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    assert resp2.json()["error_code"] == "EMAIL_ALREADY_REGISTERED"


async def test_login_success(client):
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Nishant", "email": "login@example.com", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_invalid_password(client):
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Nishant", "email": "wrongpass@example.com", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "wrongpass@example.com", "password": "wrongpassword"}
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "INVALID_CREDENTIALS"


async def test_jwt_authentication_required(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_jwt_authentication_valid_token(client):
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Nishant", "email": "me@example.com", "password": "password123"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "me@example.com", "password": "password123"}
    )
    token = login.json()["access_token"]

    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


async def test_invalid_token_rejected(client):
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
