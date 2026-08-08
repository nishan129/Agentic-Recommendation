from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# Known event types. Kept as a plain set (not a strict enum) so the frontend
# can introduce new low-risk event types without a backend deploy — event_type
# is still length-validated and stored as a string.
KNOWN_EVENT_TYPES = {
    "page_view",
    "product_view",
    "search",
    "product_click",
    "category_view",
    "recommendation_view",
    "recommendation_click",
    "add_to_cart",
    "purchase",
    "course_start",
    "course_complete",
    "wishlist_add",
    "time_spent",
    "scroll",
    "video_progress",
}


class EventCreateRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    product_id: Optional[str] = None
    session_id: Optional[str] = Field(default=None, max_length=128)
    page: Optional[str] = Field(default=None, max_length=512)
    search_query: Optional[str] = Field(default=None, max_length=512)
    metadata: Optional[dict[str, Any]] = None


class EventBatchRequest(BaseModel):
    events: list[EventCreateRequest] = Field(min_length=1)


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    session_id: Optional[str]
    event_type: str
    product_id: Optional[str]
    page: Optional[str]
    search_query: Optional[str]
    timestamp: datetime


class EventBatchResponse(BaseModel):
    success: bool = True
    accepted: int
    rejected: int
    errors: list[str] = []
