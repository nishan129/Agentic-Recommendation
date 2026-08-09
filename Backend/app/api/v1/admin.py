from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import PaginationParams, get_current_admin, pagination_params
from app.db.session import get_db
from app.models.event import UserEvent
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.product import ProductCreateRequest, ProductRead, ProductUpdateRequest
from app.services.product_service import ProductService

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(get_current_admin)])


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    """High-level counts for the admin dashboard."""
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_products = (await db.execute(select(func.count()).select_from(Product))).scalar_one()
    total_events = (await db.execute(select(func.count()).select_from(UserEvent))).scalar_one()
    total_recommendations = (await db.execute(select(func.count()).select_from(Recommendation))).scalar_one()
    return {
        "total_users": total_users,
        "total_products": total_products,
        "total_events": total_events,
        "total_recommendations": total_recommendations,
    }


@router.get("/stats/events")
async def event_stats(db: AsyncSession = Depends(get_db)):
    """Event counts grouped by type — a quick view into user activity."""
    result = await db.execute(
        select(UserEvent.event_type, func.count()).group_by(UserEvent.event_type)
    )
    return {event_type: count for event_type, count in result.all()}


@router.get("/stats/recommendations")
async def recommendation_stats(db: AsyncSession = Depends(get_db)):
    """Recommendation counts grouped by source/model version."""
    result = await db.execute(
        select(Recommendation.source, Recommendation.model_version, func.count(), func.avg(Recommendation.score))
        .group_by(Recommendation.source, Recommendation.model_version)
    )
    return [
        {"source": source, "model_version": version, "count": count, "avg_score": round(avg or 0.0, 4)}
        for source, version, count, avg in result.all()
    ]


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest,
    background_tasks: BackgroundTasks,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = ProductService(db)
    return await service.create_product(payload, created_by=admin.id,background_tasks=background_tasks)


@router.get("/products", response_model=PaginatedResponse[ProductRead])
async def list_all_products(
    pagination: PaginationParams = Depends(pagination_params),
    search: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = ProductService(db)
    items, total = await service.list_products(
        offset=pagination.offset,
        limit=pagination.limit,
        search=search,
        category=category,
        active_only=False,
    )
    total_pages = max(1, (total + pagination.limit - 1) // pagination.limit)
    return PaginatedResponse(
        items=items,
        meta=PaginationMeta(page=pagination.page, limit=pagination.limit, total=total, total_pages=total_pages),
    )


@router.get("/products/{product_id}", response_model=ProductRead)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    service = ProductService(db)
    return await service.get_product(product_id)


@router.put("/products/{product_id}", response_model=ProductRead)
@router.patch("/products/{product_id}", response_model=ProductRead)
async def update_product(product_id: str, payload: ProductUpdateRequest, db: AsyncSession = Depends(get_db)):
    service = ProductService(db)
    return await service.update_product(product_id, payload)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, db: AsyncSession = Depends(get_db)):
    service = ProductService(db)
    await service.delete_product(product_id)
