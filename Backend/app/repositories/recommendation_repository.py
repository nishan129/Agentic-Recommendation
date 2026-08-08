from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.recommendation import Recommendation


class RecommendationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_many(self, recommendations: list[Recommendation]) -> Sequence[Recommendation]:
        self.db.add_all(recommendations)
        await self.db.commit()
        return recommendations

    async def get_history_for_user(self, user_id: str, limit: int = 50) -> Sequence[Recommendation]:
        result = await self.db.execute(
            select(Recommendation)
            .options(selectinload(Recommendation.product))
            .where(Recommendation.user_id == user_id)
            .order_by(Recommendation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
