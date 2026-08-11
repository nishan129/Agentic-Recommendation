"""
User Profile Tool — the small amount of user-identity context the agent
needs (name, for a personalized narrative) plus whether they've been
recommended anything before (so the narrative can nod to "since last
time" continuity instead of always sounding like a first impression).
"""
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.user_repository import UserRepository


@dataclass
class UserProfile:
    user_id: str
    name: str
    is_returning: bool  # has at least one prior recommendation batch


async def get_user_profile(db: AsyncSession, user_id: str) -> UserProfile:
    users = UserRepository(db)
    recommendations = RecommendationRepository(db)

    user: User | None = await users.get_by_id(user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    history = await recommendations.get_history_for_user(user_id, limit=1)

    return UserProfile(
        user_id=user.id,
        name=user.name,
        is_returning=len(history) > 0,
    )
