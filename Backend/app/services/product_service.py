from typing import Optional, Sequence
import logging
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal

from app.core.exceptions import NotFoundError
from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreateRequest, ProductUpdateRequest
from app.retrieval.qdrant_services import upsert_chunks
from app.retrieval.embeddings import mesh_embed
from app.utils.product_data import create_text
import uuid

logger = logging.getLogger(__name__)

class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.products = ProductRepository(db)

    async def create_product(self,payload: ProductCreateRequest,created_by: str, background_tasks: BackgroundTasks) -> Product:
        product = Product(**payload.model_dump(), created_by=created_by)
        product = await self.products.create(product)

        # Fire-and-forget: don't block the API response on embedding
        background_tasks.add_task(self._sync_to_vector_store, product.id)

        return product
        
    async def _sync_to_vector_store(self, product_id: str) -> None:
        async with AsyncSessionLocal() as session:
            repo = ProductRepository(session)
            try:
                product = await repo.get_by_id(product_id)
                if product is None:
                    logger.warning("Product %s not found during vector sync", product_id)
                    return

                product_dict = {
                    "id": uuid.uuid4().hex,
                    "title": product.title,
                    "description": product.description,
                    "category": product.category,
                    "price": float(product.price) if product.price is not None else None,
                    "rating": product.rating,
                    "tags": product.tags or [],
                }

                text = create_text(product_dict)
                vector = mesh_embed(text)
                upsert_chunks([product_dict], vector)

                logger.info("Synced product %s to Qdrant", product_id)
            except Exception:
                logger.exception("Failed to sync product %s to Qdrant", product_id)

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
