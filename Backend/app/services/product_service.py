from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreateRequest, ProductUpdateRequest
from app.retrieval.qdrant_services import upsert_chunks
from app.retrieval.embeddings import mesh_embed
from app.utils.product_data import create_text


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.products = ProductRepository(db)

    async def create_product(self, payload: ProductCreateRequest, created_by: str) -> Product:
        product = Product(**payload.model_dump(), created_by=created_by)
        return await self.products.create(product)
        
       

    async def get_product(self, product_id: str) -> Product:
        product = await self.products.get_by_id(product_id)
        if not product:
            raise NotFoundError("Product not found", "PRODUCT_NOT_FOUND")
        return product

    async def update_product(self, product_id: str, payload: ProductUpdateRequest) -> Product:
        product = await self.get_product(product_id)
        fields = payload.model_dump(exclude_unset=True)
        return await self.products.update(product, fields)

    async def delete_product(self, product_id: str) -> None:
        product = await self.get_product(product_id)
        await self.products.delete(product)

    async def list_products(
        self,
        *,
        offset: int,
        limit: int,
        search: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        active_only: bool = True,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> tuple[Sequence[Product], int]:
        return await self.products.list_products(
            offset=offset,
            limit=limit,
            search=search,
            category=category,
            min_price=min_price,
            max_price=max_price,
            active_only=active_only,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )
