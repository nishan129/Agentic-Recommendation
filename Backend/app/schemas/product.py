from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.product import ProductType


class ProductCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field(min_length=1, max_length=100)
    product_type: ProductType = ProductType.PRODUCT
    price: float = Field(ge=0)
    image_url: Optional[str] = None
    tags: Optional[list[str]] = None
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    stock: Optional[int] = Field(default=None, ge=0)
    extra_metadata: Optional[dict[str, Any]] = None
    is_active: bool = True


class ProductUpdateRequest(BaseModel):
    """All fields optional for PATCH-style partial updates.

    Note: `created_by` and `created_at` are intentionally NOT present here —
    clients can never set or change them.
    """

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    product_type: Optional[ProductType] = None
    price: Optional[float] = Field(default=None, ge=0)
    image_url: Optional[str] = None
    tags: Optional[list[str]] = None
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    stock: Optional[int] = Field(default=None, ge=0)
    extra_metadata: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: Optional[str]
    category: str
    product_type: ProductType
    price: float
    image_url: Optional[str]
    tags: Optional[list[str]]
    rating: Optional[float]
    stock: Optional[int]
    is_active: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
