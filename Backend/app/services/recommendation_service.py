"""
RecommendationService - the seam where LangGraph agents will plug in later.

Today this implements a simple, explainable heuristic:

    User Events -> extract preferred categories/products
                -> query candidate products
                -> rank by category-affinity + rating
                -> persist + return top-N

The public method `get_recommendations` is the only thing the API route
calls. Swapping the body of this method for a LangGraph agent invocation
(User Profile Tool -> Event History Tool -> Product Search Tool -> Vector
Search Tool -> Ranking Tool) will not require any change to the router,
schemas, or repository layer.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.recommendation import Recommendation
from app.repositories.event_repository import EventRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.schemas.recommendation import RecommendationItem

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


class RecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.events = EventRepository(db)
        self.products = ProductRepository(db)
        self.recommendations = RecommendationRepository(db)

    async def get_recommendations(
        self, user_id: str, limit: int | None = None
    ) -> list[RecommendationItem]:
        limit = limit or settings.RECOMMENDATION_DEFAULT_LIMIT

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
