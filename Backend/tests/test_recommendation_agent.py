"""
Tests for the agentic recommendation pipeline. The LLM (Groq) and vector
store (Qdrant/MeshAPI) are mocked at their call boundaries — these tests
verify the *orchestration logic* (digest building, cold-start detection,
fallback behavior, persistence) without requiring live credentials or a
running Qdrant instance.
"""
from unittest.mock import patch

import pytest

from tests.conftest import get_auth_headers

pytestmark = pytest.mark.asyncio


async def _register_and_login(client, email="agent@example.com", password="password123"):
    await client.post("/api/v1/auth/register", json={"name": "Agent Tester", "email": email, "password": password})
    return await get_auth_headers(client, email, password)


FAKE_REASONING = {
    "interest_summary": "This user keeps returning to agentic AI content and searched for it twice.",
    "search_query": "advanced agentic AI and autonomous LLM systems courses",
    "confidence": "high",
}

FAKE_NARRATIVE = {
    "narrative": "Since you've been diving into agentic AI content, here's what fits your journey.",
    "product_reasons": {},  # filled in per-test with real product ids
}


async def test_agentic_cold_start_falls_back_to_heuristic(client, admin_user):
    """With too little activity, the agent should return its own
    cold-start message without calling the LLM or Qdrant at all, and the
    service should still return usable (heuristic) product items."""
    from app.core.config import settings

    admin_headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    await client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json={"title": "Popular Pick", "category": "programming", "price": 199, "rating": 4.9},
    )

    user_headers = await _register_and_login(client)

    original_engine = settings.RECOMMENDATION_ENGINE
    settings.RECOMMENDATION_ENGINE = "agentic"
    try:
        with patch("app.core.llm_client.complete_json") as mock_llm, \
             patch("app.retrieval.qdrant_services.search") as mock_search:
            resp = await client.get("/api/v1/recommendations", headers=user_headers)
            assert resp.status_code == 200
            body = resp.json()
            assert body["engine"] == "agentic_cold_start"
            assert len(body["recommendations"]) >= 1
            # Cold start never calls the LLM or vector search.
            mock_llm.assert_not_called()
            mock_search.assert_not_called()
    finally:
        settings.RECOMMENDATION_ENGINE = original_engine


async def test_agentic_pipeline_end_to_end_with_mocked_boundaries(client, admin_user):
    """With enough activity, the full pipeline should run: reasoning ->
    vector search -> narrative -> persistence as a RecommendationBatch."""
    from app.core.config import settings

    admin_headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    created = await client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json={"title": "Building Autonomous LLM Systems", "category": "ai-ml", "price": 299, "rating": 4.7},
    )
    product_id = created.json()["id"]

    user_headers = await _register_and_login(client, email="active-agent@example.com")

    # Generate enough events to clear MIN_EVENTS_FOR_PERSONALIZATION.
    for event_type in ["search", "product_view", "product_click", "search"]:
        await client.post(
            "/api/v1/events",
            headers=user_headers,
            json={"event_type": event_type, "product_id": product_id if "product" in event_type else None},
        )

    narrative_payload = dict(FAKE_NARRATIVE)
    narrative_payload["product_reasons"] = {product_id: "This matches your recent agentic AI research."}

    fake_search_result = [
        {
            "product_id": product_id,
            "title": "Building Autonomous LLM Systems",
            "category": "ai-ml",
            "description": "Advanced course",
            "price": 299.0,
            "rating": 4.7,
            "tags": [],
            "similarity_score": 0.87,
        }
    ]

    original_engine = settings.RECOMMENDATION_ENGINE
    settings.RECOMMENDATION_ENGINE = "agentic"
    try:
        with patch("app.agents.recommendation_agent.complete_json") as mock_llm, \
             patch("app.agents.tools.product_search_tool.mesh_embed") as mock_embed, \
             patch("app.agents.tools.product_search_tool.qdrant_search") as mock_search:
            mock_llm.side_effect = [FAKE_REASONING, narrative_payload]
            mock_embed.return_value = [[0.1] * 1024]
            mock_search.return_value = fake_search_result

            resp = await client.get("/api/v1/recommendations", headers=user_headers)
            assert resp.status_code == 200
            body = resp.json()

            assert body["engine"] == "agentic"
            assert body["narrative"] == narrative_payload["narrative"]
            assert len(body["recommendations"]) == 1
            rec = body["recommendations"][0]
            assert rec["product_id"] == product_id
            assert rec["source"] == "agentic"
            assert rec["reason"] == "This matches your recent agentic AI research."
            assert rec["category"] == "ai-ml"

            mock_embed.assert_called_once()
            mock_search.assert_called_once()
    finally:
        settings.RECOMMENDATION_ENGINE = original_engine

    # Verify a RecommendationBatch with the narrative was actually persisted.
    history_resp = await client.get("/api/v1/recommendations/history", headers=user_headers)
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) >= 1
    assert history[0]["batch_id"] is not None


async def test_agentic_failure_falls_back_to_heuristic(client, admin_user):
    """If the LLM call raises (timeout, bad response, etc.), the service
    must still return a usable heuristic response — never a 500."""
    from app.core.config import settings

    admin_headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    created = await client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json={"title": "Fallback Course", "category": "programming", "price": 99, "rating": 4.5},
    )
    product_id = created.json()["id"]

    user_headers = await _register_and_login(client, email="fallback-agent@example.com")
    for event_type in ["search", "product_view", "product_click", "search"]:
        await client.post(
            "/api/v1/events",
            headers=user_headers,
            json={"event_type": event_type, "product_id": product_id if "product" in event_type else None},
        )

    original_engine = settings.RECOMMENDATION_ENGINE
    settings.RECOMMENDATION_ENGINE = "agentic"
    try:
        with patch("app.agents.recommendation_agent.complete_json") as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM provider timeout")

            resp = await client.get("/api/v1/recommendations", headers=user_headers)
            assert resp.status_code == 200
            body = resp.json()
            assert body["engine"] == "heuristic"
            assert body["narrative"] is None
    finally:
        settings.RECOMMENDATION_ENGINE = original_engine


async def test_heuristic_engine_unaffected_by_default(client, admin_user):
    """Default config (RECOMMENDATION_ENGINE=heuristic) must never import
    or touch the agent pipeline at all."""
    admin_headers = await get_auth_headers(client, "admin@example.com", "adminpass123")
    await client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json={"title": "Default Engine Product", "category": "design", "price": 49, "rating": 4.0},
    )
    user_headers = await _register_and_login(client, email="default-engine@example.com")

    resp = await client.get("/api/v1/recommendations", headers=user_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["engine"] == "heuristic_cold_start" or body["engine"] == "heuristic"
    assert body["narrative"] is None
