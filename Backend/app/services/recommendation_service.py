"""
RecommendationService — thin wrapper around RecommendationAgent
(app/agent/recommendation_agent.py). All recommendations come from the
agentic pipeline: event history -> LLM intent reasoning -> Qdrant vector
search -> LLM narrative generation. No heuristic fallback is mixed into
the response — if the agent has nothing (cold start, LLM/Qdrant failure),
the response reflects that honestly instead of silently substituting
popular-product picks.

The public method `get_recommendations` is the only thing the API route
calls, returning a RecommendationResult with the narrative and per-product
items produced by the agent.
"""
import logging
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


@dataclass
class RecommendationResult:
    items: list[RecommendationItem] = field(default_factory=list)
    narrative: Optional[str] = None
    engine: str = "agentic"
    is_cold_start: bool = False


class RecommendationAgentError(Exception):
    """Raised when the agent pipeline fails outright (LLM timeout, Qdrant
    unreachable, bad JSON, etc.) — the route decides how to surface this
    to the client rather than the service silently masking it."""


class RecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.events = EventRepository(db)
        self.products = ProductRepository(db)
        self.recommendations = RecommendationRepository(db)

    async def get_recommendations(self, user_id: str, limit: int | None = None) -> RecommendationResult:
        limit = limit or settings.RECOMMENDATION_DEFAULT_LIMIT

        from app.agent.recommendation_agent import RecommendationAgent

        agent = RecommendationAgent()
        try:
            result = await agent.generate(self.db, user_id, top_k=limit)
        except Exception as exc:
            logger.exception("Agentic recommendation pipeline failed for user %s", user_id)
            raise RecommendationAgentError(str(exc)) from exc

        if result.is_cold_start or not result.products:
            # No heuristic substitution — return the agent's own
            # cold-start narrative with an empty product list, so the
            # frontend can render "still learning your preferences"
            # honestly instead of showing unrelated popular picks
            # labeled as personalized recommendations.
            return RecommendationResult(
                items=[],
                narrative=result.narrative,
                engine="agentic",
                is_cold_start=True,
            )

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