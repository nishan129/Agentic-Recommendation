
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import (
    INTENT_REASONING_SYSTEM_PROMPT,
    NARRATIVE_SYSTEM_PROMPT,
    build_narrative_user_prompt,
    build_reasoning_user_prompt,
)
from app.agent.tools.event_history_tool import EventDigest, get_event_digest
from app.agent.tools.product_search_tool import SimilarProduct, search_similar_products
from app.agent.tools.user_profile_tool import get_user_profile, UserProfile
from app.core.llm_client import complete_json

logger = logging.getLogger(__name__)

MIN_EVENTS_FOR_PERSONALIZATION = 3

# Hard ceiling — a caller passing top_k=50 should never turn into 50 LLM-
# justified recommendations; cap it once, here, so every node downstream
# (vector search top_k, narrative prompt, response payload) agrees.
MAX_RECOMMENDATIONS = 10


@dataclass
class RecommendedProduct:
    product_id: str
    title: str
    category: str | None
    price: float | None
    rating: float | None
    similarity_score: float
    reason: str


@dataclass
class AgentRecommendationResult:
    narrative: str
    products: list[RecommendedProduct] = field(default_factory=list)
    interest_summary: str = ""
    confidence: str = "low"
    is_cold_start: bool = False


class AgentState(TypedDict, total=False):
    db: AsyncSession
    user_id: str
    top_k: int
    profile: UserProfile
    digest: EventDigest
    reasoning: dict
    candidates: list[SimilarProduct]
    narrative_payload: dict
    result: AgentRecommendationResult


async def _load_context_node(state: AgentState) -> AgentState:
    """Fetch profile + event digest in parallel — first node in the graph."""
    profile, digest = await asyncio.gather(
        get_user_profile(state["db"], state["user_id"]),
        get_event_digest(state["db"], state["user_id"]),
    )
    return {**state, "profile": profile, "digest": digest}


async def _reason_intent_node(state: AgentState) -> AgentState:
    digest: EventDigest = state["digest"]
    reasoning = await asyncio.to_thread(
        complete_json,
        INTENT_REASONING_SYSTEM_PROMPT,
        build_reasoning_user_prompt(digest.to_prompt_text()),
    )
    return {**state, "reasoning": reasoning}


async def _search_products_node(state: AgentState) -> AgentState:
    reasoning = state["reasoning"]
    digest: EventDigest = state["digest"]
    top_k = state["top_k"]

    candidates = await asyncio.to_thread(
        search_similar_products,
        reasoning["search_query"],
        top_k,
        digest.seen_product_ids,
    )
    if len(candidates) < top_k:
        logger.info(
            "Vector search returned %d/%d candidates for user %s",
            len(candidates), top_k, state["user_id"],
        )
    return {**state, "candidates": candidates}


async def _generate_narrative_node(state: AgentState) -> AgentState:
    candidates: list[SimilarProduct] = state["candidates"]
    profile: UserProfile = state["profile"]
    reasoning = state["reasoning"]

    products_for_prompt = [
        {
            "product_id": c.product_id,
            "title": c.title,
            "category": c.category,
            "price": c.price,
            "rating": c.rating,
        }
        for c in candidates
    ]
    narrative_payload = await asyncio.to_thread(
        complete_json,
        NARRATIVE_SYSTEM_PROMPT,
        build_narrative_user_prompt(
            profile.name, reasoning["interest_summary"], products_for_prompt, profile.is_returning
        ),
    )

    products = [
        RecommendedProduct(
            product_id=c.product_id,
            title=c.title,
            category=c.category,
            price=c.price,
            rating=c.rating,
            similarity_score=c.similarity_score,
            reason=narrative_payload.get("product_reasons", {}).get(
                c.product_id, f"A strong match based on your recent activity in {c.category}."
            ),
        )
        for c in candidates
    ]

    result = AgentRecommendationResult(
        narrative=narrative_payload["narrative"],
        products=products,
        interest_summary=reasoning["interest_summary"],
        confidence=reasoning.get("confidence", "medium"),
        is_cold_start=False,
    )
    return {**state, "result": result}


async def _cold_start_node(state: AgentState) -> AgentState:
    """Not enough behavioral signal yet (or vector search came up empty)
    for real personalization. Caller (RecommendationService) is expected
    to fall back to the heuristic engine's popular-products query in this
    case rather than the agent inventing interests from nothing."""
    profile: UserProfile = state["profile"]
    result = AgentRecommendationResult(
        narrative=(
            f"Hey {profile.name} — we're still learning what you're into. "
            "Here are some well-rounded picks to get started; recommendations "
            "will sharpen the more you explore."
        ),
        products=[],
        interest_summary="",
        confidence="low",
        is_cold_start=True,
    )
    return {**state, "result": result}


def _route_after_load(state: AgentState) -> str:
    digest: EventDigest = state["digest"]
    if digest.is_empty() or len(digest.items) < MIN_EVENTS_FOR_PERSONALIZATION:
        return "cold_start"
    return "reason_intent"


def _route_after_search(state: AgentState) -> str:
    if not state["candidates"]:
        return "cold_start"
    return "generate_narrative"


def _build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("load_context", _load_context_node)
    graph.add_node("reason_intent", _reason_intent_node)
    graph.add_node("search_products", _search_products_node)
    graph.add_node("generate_narrative", _generate_narrative_node)
    graph.add_node("cold_start", _cold_start_node)

    graph.set_entry_point("load_context")
    graph.add_conditional_edges(
        "load_context", _route_after_load, {"reason_intent": "reason_intent", "cold_start": "cold_start"}
    )
    graph.add_edge("reason_intent", "search_products")
    graph.add_conditional_edges(
        "search_products",
        _route_after_search,
        {"generate_narrative": "generate_narrative", "cold_start": "cold_start"},
    )
    graph.add_edge("generate_narrative", END)
    graph.add_edge("cold_start", END)

    return graph.compile()


_compiled_graph = _build_graph()


class RecommendationAgent:
    """Stateless orchestrator — safe to instantiate per-call."""

    async def generate(
        self,
        db: AsyncSession,
        user_id: str,
        top_k: int = 6,
    ) -> AgentRecommendationResult:
        top_k = min(top_k, MAX_RECOMMENDATIONS)

        final_state: AgentState = await _compiled_graph.ainvoke(
            {"db": db, "user_id": user_id, "top_k": top_k}
        )
        return final_state["result"]