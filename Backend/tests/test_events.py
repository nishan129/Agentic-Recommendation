import asyncio

import pytest

from tests.conftest import get_auth_headers

pytestmark = pytest.mark.asyncio


async def _register_and_login(client, email="events@example.com", password="password123"):
    await client.post("/api/v1/auth/register", json={"name": "User", "email": email, "password": password})
    return await get_auth_headers(client, email, password)


async def test_create_event(client):
    headers = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/events",
        headers=headers,
        json={"event_type": "page_view", "page": "/home", "session_id": "s1"},
    )
    assert resp.status_code == 202
    assert resp.json()["success"] is True


async def test_create_event_requires_auth(client):
    resp = await client.post("/api/v1/events", json={"event_type": "page_view"})
    assert resp.status_code == 401


async def test_batch_events(client):
    headers = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/events/batch",
        headers=headers,
        json={
            "events": [
                {"event_type": "product_click", "product_id": "p1"},
                {"event_type": "time_spent", "product_id": "p1", "metadata": {"duration_seconds": 30}},
            ]
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] == 2
    assert body["rejected"] == 0


async def test_batch_events_empty_rejected_by_validation(client):
    headers = await _register_and_login(client)
    resp = await client.post("/api/v1/events/batch", headers=headers, json={"events": []})
    assert resp.status_code == 422


async def test_invalid_event_missing_type(client):
    headers = await _register_and_login(client)
    resp = await client.post("/api/v1/events", headers=headers, json={"page": "/home"})
    assert resp.status_code == 422


async def test_unauthorized_batch_event(client):
    resp = await client.post("/api/v1/events/batch", json={"events": [{"event_type": "page_view"}]})
    assert resp.status_code == 401


async def test_batch_too_large_rejected(client):
    headers = await _register_and_login(client)
    events = [{"event_type": "product_view", "product_id": f"p{i}"} for i in range(200)]
    resp = await client.post("/api/v1/events/batch", headers=headers, json={"events": events})
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "BATCH_TOO_LARGE"
