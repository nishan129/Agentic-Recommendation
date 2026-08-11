"""
RecommendationService — routes between two engines behind a feature flag
(settings.RECOMMENDATION_ENGINE = "heuristic" | "agentic"):

    heuristic: category-affinity scoring (see _get_heuristic_recommendations)
    agentic:   RecommendationAgent pipeline — event history -> LLM intent
               reasoning -> Qdrant vector search -> LLM narrative generation
               (see app/agents/recommendation_agent.py)

The agentic path ALWAYS falls back to the heuristic path on any failure
(LLM timeout, Qdrant unreachable, bad JSON output, etc.) — a recommendation
page must never break just because an external AI service hiccuped. This
mirrors the same "never let a background system break the user-facing
site" principle used throughout event tracking.

The public method `get_recommendations` is the only thing the API route
calls, returning a RecommendationResult that includes the narrative (only
populated by the agentic engine) alongside the usual per-product items.
"""
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.recommendation import Recommendation, RecommendationBatch
from app.repositories.event_repository import EventRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.schemas.recommendation import RecommendationItem

logger = logging.getLogger(__name__)

# Event types that signal positive interest, weighted by strength of signal.
INTEREST_WEIGHTS: dict[str, float] = {
    "purchase": 5.0,
    "add_to_cart": 3.0,
    "wishlist_add": 3.0,
    "course_complete": 4.0,
    "course_start": 2.0,
    "product_click": 1.5,
    "recommendation_click": 1.5,
    "product_view": 1.0,
    "search": 0.5,
    "category_view": 0.75,
}


@dataclass
class RecommendationResult:
    items: list[RecommendationItem] = field(default_factory=list)
    narrative: Optional[str] = None
    engine: str = "heuristic"


class RecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.events = EventRepository(db)
        self.products = ProductRepository(db)
        self.recommendations = RecommendationRepository(db)

    async def get_recommendations(self, user_id: str, limit: int | None = None) -> RecommendationResult:
        limit = limit or settings.RECOMMENDATION_DEFAULT_LIMIT

        if settings.RECOMMENDATION_ENGINE == "agentic":
            try:
                return await self._get_agentic_recommendations(user_id, limit)
            except Exception:
                logger.exception(
                    "Agentic recommendation pipeline failed for user %s — falling back to heuristic", user_id
                )

        items = await self._get_heuristic_recommendations(user_id, limit)
        return RecommendationResult(items=items, narrative=None, engine="heuristic")

    async def _get_agentic_recommendations(self, user_id: str, limit: int) -> RecommendationResult:
        # Imported lazily so environments running heuristic-only never need
        # GROQ_API_KEY / MESHAPI_TOKEN / a reachable Qdrant just to import
        # this service module.
        from app.agents.recommendation_agent import RecommendationAgent

        agent = RecommendationAgent()
        result = await agent.generate(self.db, user_id, top_k=limit)

        if result.is_cold_start or not result.products:
            items = await self._get_heuristic_recommendations(user_id, limit)
            return RecommendationResult(items=items, narrative=result.narrative, engine="agentic_cold_start")

        items = [
            RecommendationItem(
                product_id=p.product_id,
                title=p.title,
                score=p.similarity_score,
                reason=p.reason,
                source="agentic",
                model_version=settings.RECOMMENDATION_MODEL_VERSION,
                price=p.price,
                category=p.category,
            )
            for p in result.products
        ]

        await self._persist_batch(
            user_id=user_id,
            items=items,
            narrative=result.narrative,
            interest_summary=result.interest_summary,
            confidence=result.confidence,
        )
        return RecommendationResult(items=items, narrative=result.narrative, engine="agentic")

    async def _get_heuristic_recommendations(self, user_id: str, limit: int) -> list[RecommendationItem]:
        recent_events = await self.events.get_recent_for_user(user_id, limit=200)

        category_scores: Counter[str] = Counter()
        seen_product_ids: set[str] = set()
        for event in recent_events:
            weight = INTEREST_WEIGHTS.get(event.event_type, 0.0)
            if weight <= 0:
                continue
            if event.product_id:
                seen_product_ids.add(event.product_id)
                product = await self.products.get_by_id(event.product_id)
                if product:
                    category_scores[product.category] += weight

        if not category_scores:
            # Cold start: no signal yet, fall back to top-rated active products.
            candidates, _ = await self.products.list_products(
                offset=0, limit=limit, active_only=True, sort_by="rating", sort_desc=True
            )
            items = [
                RecommendationItem(
                    product_id=p.id,
                    title=p.title,
                    score=round((p.rating or 0.0) / 5.0, 4),
                    reason="Popular pick while we learn your preferences",
                    source="heuristic_cold_start",
                    model_version=settings.RECOMMENDATION_MODEL_VERSION,
                    image_url=p.image_url,
                    price=p.price,
                    category=p.category,
                )
                for p in candidates
            ]
            await self._persist(user_id, items)
            return items

        top_categories = [cat for cat, _ in category_scores.most_common(3)]
        max_score = max(category_scores.values())

        items: list[RecommendationItem] = []
        for category in top_categories:
            candidates, _ = await self.products.list_products(
                offset=0,
                limit=limit,
                category=category,
                active_only=True,
                sort_by="rating",
                sort_desc=True,
            )
            for product in candidates:
                if product.id in seen_product_ids:
                    continue  # don't recommend what they already interacted with
                if any(item.product_id == product.id for item in items):
                    continue
                affinity = category_scores[category] / max_score
                rating_boost = (product.rating or 3.0) / 5.0
                score = round(0.7 * affinity + 0.3 * rating_boost, 4)
                items.append(
                    RecommendationItem(
                        product_id=product.id,
                        title=product.title,
                        score=score,
                        reason=f"Based on your recent interest in {category}",
                        source="heuristic",
                        model_version=settings.RECOMMENDATION_MODEL_VERSION,
                        image_url=product.image_url,
                        price=product.price,
                        category=product.category,
                    )
                )

        items.sort(key=lambda i: i.score, reverse=True)
        items = items[:limit]
        await self._persist(user_id, items)
        return items

    async def _persist(self, user_id: str, items: list[RecommendationItem]) -> None:
        if not items:
            return
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        rows = [
            Recommendation(
                user_id=user_id,
                product_id=item.product_id,
                score=item.score,
                reason=item.reason,
                source=item.source,
                model_version=item.model_version,
                expires_at=expires_at,
            )
            for item in items
        ]
        await self.recommendations.save_many(rows)

    async def _persist_batch(
        self,
        user_id: str,
        items: list[RecommendationItem],
        narrative: str,
        interest_summary: str,
        confidence: str,
    ) -> None:
        if not items:
            return
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        batch = RecommendationBatch(
            user_id=user_id,
            narrative=narrative,
            interest_summary=interest_summary,
            trigger_source="on_demand",
            confidence=confidence,
            model_version=settings.RECOMMENDATION_MODEL_VERSION,
            expires_at=expires_at,
        )
        rows = [
            Recommendation(
                user_id=user_id,
                product_id=item.product_id,
                score=item.score,
                reason=item.reason,
                source=item.source,
                model_version=item.model_version,
                expires_at=expires_at,
            )
            for item in items
        ]
        await self.recommendations.save_batch(batch, rows)
