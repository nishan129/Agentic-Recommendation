"""
Declarative base shared by all ORM models, plus a common TimestampMixin.

`base_import_all_models` is imported by Alembic's env.py so that
`Base.metadata` is fully populated for autogenerate.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def new_uuid() -> str:
    return str(uuid.uuid4())


def base_import_all_models() -> None:
    """Import all model modules so they register on Base.metadata."""
    from app.models import event, product, recommendation, user  # noqa: F401
