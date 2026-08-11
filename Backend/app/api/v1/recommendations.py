from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.recommendation import RecommendationHistoryItem, RecommendationResponse

from app.services.recommendation_service import RecommendationAgentError, RecommendationService

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])



@router.get("", response_model=RecommendationResponse)
async def get_recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = RecommendationService(db)
    try:
        result = await service.get_recommendations(current_user.id, limit=limit)
    except RecommendationAgentError:
        return RecommendationResponse(
            user_id=current_user.id, recommendations=[], narrative=None, engine="agentic"
        )
    return RecommendationResponse(
        user_id=current_user.id,
        recommendations=result.items,
        narrative=result.narrative,
        engine=result.engine,
    )

@router.get("/history", response_model=list[RecommendationHistoryItem])
async def get_recommendation_history(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.recommendation_repository import RecommendationRepository

    repo = RecommendationRepository(db)
    return await repo.get_history_for_user(current_user.id, limit=limit)