import asyncio

import pytest

from tests.conftest import get_auth_headers

pytestmark = pytest.mark.asyncio


async def _register_and_login(client, email="rec@example.com", password="password123"):
    await client.post("/api/v1/auth/register", json={"name": "User", "email": email, "password": password})
    return await get_auth_headers(client, email, password)


async def test_get_recommendations_cold_start(client, admin_user):
    """With no event history, recommendations fall back to top-rated products."""
    admin_headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    await client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json={"title": "Top Rated Course", "category": "programming", "price": 199, "rating": 4.9},
    )

    user_headers = await _register_and_login(client)
    resp = await client.get("/api/v1/recommendations", headers=user_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "recommendations" in body
    assert len(body["recommendations"]) >= 1
    assert body["recommendations"][0]["source"] == "heuristic_cold_start"


async def test_recommendations_require_auth(client):
    resp = await client.get("/api/v1/recommendations")
    assert resp.status_code == 401


async def test_recommendations_reflect_user_events(client, admin_user):
    admin_headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    viewed = await client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json={"title": "Python Deep Dive", "category": "programming", "price": 299, "rating": 4.5},
    )
    viewed_id = viewed.json()["id"]

    other = await client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json={"title": "Python for Data Science", "category": "programming", "price": 399, "rating": 4.2},
    )
    other_id = other.json()["id"]

    user_headers = await _register_and_login(client, email="active@example.com")

    event_resp = await client.post(
        "/api/v1/events",
        headers=user_headers,
        json={"event_type": "purchase", "product_id": viewed_id},
    )
    assert event_resp.status_code == 202

    resp = await client.get("/api/v1/recommendations", headers=user_headers)
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    # The purchased product should be excluded; the sibling in the same
    # category should be recommended.
    product_ids = [r["product_id"] for r in recs]
    assert viewed_id not in product_ids
    assert other_id in product_ids


async def test_recommendation_history(client, admin_user):
    admin_headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    await client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json={"title": "History Course", "category": "history", "price": 99, "rating": 4.0},
    )

    user_headers = await _register_and_login(client, email="history@example.com")
    await client.get("/api/v1/recommendations", headers=user_headers)

    resp = await client.get("/api/v1/recommendations/history", headers=user_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


async def test_recommendation_stats_admin_only(client, admin_user):
    admin_headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    resp = await client.get("/api/v1/admin/stats/recommendations", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
