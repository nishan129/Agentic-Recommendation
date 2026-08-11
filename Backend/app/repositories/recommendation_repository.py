from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.recommendation import Recommendation, RecommendationBatch


class RecommendationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_many(self, recommendations: list[Recommendation]) -> Sequence[Recommendation]:
        self.db.add_all(recommendations)
        await self.db.commit()
        return recommendations

    async def save_batch(
        self, batch: RecommendationBatch, recommendations: list[Recommendation]
    ) -> RecommendationBatch:
        """Persist a batch and its recommendations together in one
        transaction — either both are saved, or neither is.

        Note: batch.id (a Python-side `default=new_uuid`) is only
        assigned by SQLAlchemy at flush time, not at object construction
        — so we must add+flush the batch FIRST to get a real id before
        stamping it onto the recommendation rows below.
        """
        self.db.add(batch)
        await self.db.flush()

        for rec in recommendations:
            rec.batch_id = batch.id
        self.db.add_all(recommendations)
        await self.db.commit()
        await self.db.refresh(batch)
        return batch

    async def get_history_for_user(self, user_id: str, limit: int = 50) -> Sequence[Recommendation]:
        result = await self.db.execute(
            select(Recommendation)
            .options(selectinload(Recommendation.product))
            .where(Recommendation.user_id == user_id)
            .order_by(Recommendation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_latest_batch_for_user(self, user_id: str) -> Optional[RecommendationBatch]:
        result = await self.db.execute(
            select(RecommendationBatch)
            .options(selectinload(RecommendationBatch.recommendations).selectinload(Recommendation.product))
            .where(RecommendationBatch.user_id == user_id)
            .order_by(RecommendationBatch.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
