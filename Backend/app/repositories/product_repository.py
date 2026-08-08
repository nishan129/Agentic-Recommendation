from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


class ProductRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        return await self.db.get(Product, product_id)

    async def create(self, product: Product) -> Product:
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def update(self, product: Product, fields: dict) -> Product:
        for key, value in fields.items():
            setattr(product, key, value)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        await self.db.delete(product)
        await self.db.commit()

    async def list_products(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        active_only: bool = True,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> tuple[Sequence[Product], int]:
        query = select(Product)
        count_query = select(func.count()).select_from(Product)

        conditions = []
        if active_only:
            conditions.append(Product.is_active.is_(True))
        if search:
            like = f"%{search}%"
            conditions.append(or_(Product.title.ilike(like), Product.description.ilike(like)))
        if category:
            conditions.append(Product.category == category)
        if min_price is not None:
            conditions.append(Product.price >= min_price)
        if max_price is not None:
            conditions.append(Product.price <= max_price)

        for cond in conditions:
            query = query.where(cond)
            count_query = count_query.where(cond)

        sort_column = getattr(Product, sort_by, Product.created_at)
        query = query.order_by(sort_column.desc() if sort_desc else sort_column.asc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        total_result = await self.db.execute(count_query)
        return result.scalars().all(), total_result.scalar_one()
