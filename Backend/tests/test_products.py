import pytest

from tests.conftest import get_auth_headers

pytestmark = pytest.mark.asyncio


async def _register_and_login(client, email="user@example.com", password="password123"):
    await client.post("/api/v1/auth/register", json={"name": "User", "email": email, "password": password})
    return await get_auth_headers(client, email, password)


async def test_admin_can_create_product(client, admin_user):
    headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    resp = await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={"title": "Advanced Python", "category": "programming", "price": 999, "product_type": "course"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Advanced Python"
    assert body["created_by"] == admin_user.id


async def test_user_cannot_access_admin_api(client):
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/admin/dashboard", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NOT_AUTHORIZED"


async def test_admin_can_access_admin_api(client, admin_user):
    headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    resp = await client.get("/api/v1/admin/dashboard", headers=headers)
    assert resp.status_code == 200
    assert "total_users" in resp.json()


async def test_user_cannot_create_admin_products_when_router_protected(client):
    """Unauthenticated requests to admin product creation must be rejected."""
    resp = await client.post(
        "/api/v1/admin/products", json={"title": "Hack", "category": "x", "price": 1}
    )
    assert resp.status_code == 401


async def test_get_product(client, admin_user):
    headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    create = await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={"title": "Django Basics", "category": "programming", "price": 499},
    )
    product_id = create.json()["id"]

    resp = await client.get(f"/api/v1/products/{product_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Django Basics"


async def test_get_product_not_found(client):
    resp = await client.get("/api/v1/products/nonexistent-id")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "PRODUCT_NOT_FOUND"


async def test_update_product(client, admin_user):
    headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    create = await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={"title": "Old Title", "category": "programming", "price": 100},
    )
    product_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/admin/products/{product_id}", headers=headers, json={"title": "New Title", "price": 150}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "New Title"
    assert body["price"] == 150


async def test_delete_product(client, admin_user):
    headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    create = await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={"title": "To Delete", "category": "programming", "price": 10},
    )
    product_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/admin/products/{product_id}", headers=headers)
    assert resp.status_code == 204

    check = await client.get(f"/api/v1/products/{product_id}")
    assert check.status_code == 404


async def test_search_products(client, admin_user):
    headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={"title": "Learn Python", "category": "programming", "price": 100},
    )
    await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={"title": "Guitar Basics", "category": "music", "price": 50},
    )

    resp = await client.get("/api/v1/products", params={"search": "python"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Learn Python"

    resp2 = await client.get("/api/v1/products", params={"category": "music"})
    assert resp2.status_code == 200
    assert len(resp2.json()["items"]) == 1

    resp3 = await client.get("/api/v1/products", params={"min_price": 80, "max_price": 200})
    assert resp3.status_code == 200
    assert len(resp3.json()["items"]) == 1
    assert resp3.json()["items"][0]["title"] == "Learn Python"


async def test_client_cannot_set_created_by_or_created_at(client, admin_user):
    headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    resp = await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={
            "title": "Sneaky",
            "category": "programming",
            "price": 10,
            "created_by": "someone-else",
            "created_at": "2000-01-01T00:00:00",
        },
    )
    # extra fields are simply ignored by the schema; creator is always the authenticated admin
    assert resp.status_code == 201
    assert resp.json()["created_by"] == admin_user.id
