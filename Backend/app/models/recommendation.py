from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class RecommendationBatch(Base):
    """One agent "run" for a user: a shared narrative plus the group of
    individual Recommendation rows it produced. Exists separately from
    Recommendation because a narrative is written once per batch, not
    once per product — this is what lets the agent say "here's why these
    fit together" instead of just listing scored items."""

    __tablename__ = "recommendation_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interest_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_source: Mapped[str] = mapped_column(String(30), default="on_demand", nullable=False)
    confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
    recommendations: Mapped[List["Recommendation"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RecommendationBatch id={self.id} user_id={self.user_id}>"


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("recommendation_batches.id", ondelete="CASCADE"), nullable=True, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="heuristic", nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="recommendations")
    product: Mapped["Product"] = relationship(back_populates="recommendations")
    batch: Mapped[Optional["RecommendationBatch"]] = relationship(back_populates="recommendations")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Recommendation user_id={self.user_id} product_id={self.product_id} score={self.score}>"
