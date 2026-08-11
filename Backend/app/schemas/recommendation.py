from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RecommendationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    title: str
    score: float
    reason: str
    source: str
    model_version: str
    image_url: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None


class RecommendationResponse(BaseModel):
    user_id: str
    recommendations: list[RecommendationItem]
    narrative: Optional[str] = None
    """Short persuasive message from the agent explaining why this batch
    fits the user right now. None when served by the heuristic engine or
    during a cold-start (not enough behavioral signal yet)."""
    engine: str = "heuristic"
    """Which engine produced this batch: "heuristic" or "agentic" — lets
    the frontend/analytics distinguish them without guessing from shape."""


class RecommendationHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    score: float
    reason: Optional[str]
    source: str
    model_version: str
    created_at: datetime
    batch_id: Optional[str] = None


class RecommendationBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    narrative: Optional[str]
    interest_summary: Optional[str]
    trigger_source: str
    confidence: Optional[str]
    created_at: datetime
    recommendations: list[RecommendationItem] = []
