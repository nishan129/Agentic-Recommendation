import enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.event import UserEvent
    from app.models.recommendation import Recommendation
    from app.models.user import User


class ProductType(str, enum.Enum):
    PRODUCT = "product"
    COURSE = "course"


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_type: Mapped[ProductType] = mapped_column(
        Enum(ProductType, native_enum=False, length=20), default=ProductType.PRODUCT, nullable=False
    )
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stock: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    creator: Mapped[Optional["User"]] = relationship(back_populates="created_products")
    events: Mapped[List["UserEvent"]] = relationship(back_populates="product")
    recommendations: Mapped[List["Recommendation"]] = relationship(back_populates="product")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product id={self.id} title={self.title!r}>"
