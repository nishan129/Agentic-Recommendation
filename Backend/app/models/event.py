from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class UserEvent(Base):
    """
    Behavioral event captured from the frontend. This table is designed to
    absorb high write volume (product views, clicks, searches, time-spent
    pings, etc). It intentionally has NO updated_at — events are immutable
    once written.
    """

    __tablename__ = "user_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    page: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    search_query: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user: Mapped["User"] = relationship(back_populates="events")
    product: Mapped[Optional["Product"]] = relationship(back_populates="events")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserEvent id={self.id} type={self.event_type} user_id={self.user_id}>"
