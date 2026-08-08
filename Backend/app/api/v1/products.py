from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import PaginationParams, pagination_params
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.product import ProductRead
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=PaginatedResponse[ProductRead])
async def list_products(
    pagination: PaginationParams = Depends(pagination_params),
    search: Optional[str] = Query(default=None, description="Full-text search on title/description"),
    category: Optional[str] = Query(default=None),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    sort_by: str = Query(default="created_at", pattern="^(created_at|price|rating|title)$"),
    sort_desc: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    service = ProductService(db)
    items, total = await service.list_products(
        offset=pagination.offset,
        limit=pagination.limit,
        search=search,
        category=category,
        min_price=min_price,
        max_price=max_price,
        active_only=True,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )
    total_pages = max(1, (total + pagination.limit - 1) // pagination.limit)
    return PaginatedResponse(
        items=items,
        meta=PaginationMeta(page=pagination.page, limit=pagination.limit, total=total, total_pages=total_pages),
    )


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    service = ProductService(db)
    return await service.get_product(product_id)
