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


class RecommendationResponse(BaseModel):
    user_id: str
    recommendations: list[RecommendationItem]


class RecommendationHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    score: float
    reason: Optional[str]
    source: str
    model_version: str
    created_at: datetime
