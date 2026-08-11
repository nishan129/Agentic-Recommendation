"""
The recommendation agent — orchestrates the full pipeline:

    event history --> intent reasoning (LLM) --> vector search (Qdrant)
        --> rank/filter --> narrative generation (LLM) --> result

This is the piece that plugs into RecommendationService (see
app/services/recommendation_service.py) behind the RECOMMENDATION_ENGINE
feature flag. It never touches the database for writes — it returns a
plain result object; persistence stays in the service/repository layer,
same as the rest of the codebase.

Every external call (LLM, Qdrant/MeshAPI) is synchronous under the hood;
this module wraps them with asyncio.to_thread so the agent's own public
methods are async and don't block the event loop while waiting on network
calls, whether invoked from a request handler or a BackgroundTask.
"""
import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import (
    INTENT_REASONING_SYSTEM_PROMPT,
    NARRATIVE_SYSTEM_PROMPT,
    build_narrative_user_prompt,
    build_reasoning_user_prompt,
)
from app.agents.tools.event_history_tool import EventDigest, get_event_digest
from app.agents.tools.product_search_tool import SimilarProduct, search_similar_products
from app.agents.tools.user_profile_tool import get_user_profile
from app.core.llm_client import complete_json, complete_text

logger = logging.getLogger(__name__)

MIN_EVENTS_FOR_PERSONALIZATION = 3


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


class RecommendationAgent:
    """Stateless orchestrator — safe to instantiate per-call."""

    async def generate(
        self,
        db: AsyncSession,
        user_id: str,
        top_k: int = 6,
    ) -> AgentRecommendationResult:
        profile = await get_user_profile(db, user_id)
        digest = await get_event_digest(db, user_id)

        if digest.is_empty() or len(digest.items) < MIN_EVENTS_FOR_PERSONALIZATION:
            return await self._cold_start(profile.name, top_k)

        reasoning = await self._reason_about_intent(digest)

        candidates = await asyncio.to_thread(
            search_similar_products,
            reasoning["search_query"],
            top_k,
            digest.seen_product_ids,
        )

        if not candidates:
            logger.info("Vector search returned no candidates for user %s; falling back to cold start", user_id)
            return await self._cold_start(profile.name, top_k)

        narrative_payload = await asyncio.to_thread(
            self._generate_narrative,
            profile.name,
            reasoning["interest_summary"],
            candidates,
            profile.is_returning,
        )

        products = [
            RecommendedProduct(
                product_id=c.product_id,
                title=c.title,
                category=c.category,
                price=c.price,
                rating=c.rating,
                similarity_score=c.similarity_score,
                reason=narrative_payload["product_reasons"].get(
                    c.product_id, f"A strong match based on your recent activity in {c.category}."
                ),
            )
            for c in candidates
        ]

        return AgentRecommendationResult(
            narrative=narrative_payload["narrative"],
            products=products,
            interest_summary=reasoning["interest_summary"],
            confidence=reasoning.get("confidence", "medium"),
            is_cold_start=False,
        )

    async def _reason_about_intent(self, digest: EventDigest) -> dict:
        return await asyncio.to_thread(
            complete_json,
            INTENT_REASONING_SYSTEM_PROMPT,
            build_reasoning_user_prompt(digest.to_prompt_text()),
        )

    def _generate_narrative(
        self,
        user_name: str,
        interest_summary: str,
        candidates: list[SimilarProduct],
        is_returning: bool,
    ) -> dict:
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
        return complete_json(
            NARRATIVE_SYSTEM_PROMPT,
            build_narrative_user_prompt(user_name, interest_summary, products_for_prompt, is_returning),
        )

    async def _cold_start(self, user_name: str, top_k: int) -> AgentRecommendationResult:
        """Not enough behavioral signal yet for real personalization.
        Caller (RecommendationService) is expected to fall back to the
        heuristic engine's popular-products query in this case rather
        than the agent inventing interests from nothing."""
        return AgentRecommendationResult(
            narrative=(
                f"Hey {user_name} — we're still learning what you're into. "
                "Here are some well-rounded picks to get started; recommendations "
                "will sharpen the more you explore."
            ),
            products=[],
            interest_summary="",
            confidence="low",
            is_cold_start=True,
        )
