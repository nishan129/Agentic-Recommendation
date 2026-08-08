from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import UserEvent


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_many(self, events: list[UserEvent]) -> Sequence[UserEvent]:
        """Bulk-insert events in a single transaction (one round trip)."""
        self.db.add_all(events)
        await self.db.commit()
        return events

    async def get_recent_for_user(self, user_id: str, limit: int = 50) -> Sequence[UserEvent]:
        result = await self.db.execute(
            select(UserEvent)
            .where(UserEvent.user_id == user_id)
            .order_by(UserEvent.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()
