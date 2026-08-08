"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-08

Creates: users, products, user_events, recommendations
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("product_type", sa.String(length=20), nullable=False, server_default="product"),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_products_title", "products", ["title"])
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_is_active", "products", ["is_active"])

    op.create_table(
        "user_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("page", sa.String(length=512), nullable=True),
        sa.Column("search_query", sa.String(length=512), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_events_user_id", "user_events", ["user_id"])
    op.create_index("ix_user_events_event_type", "user_events", ["event_type"])
    op.create_index("ix_user_events_timestamp", "user_events", ["timestamp"])
    op.create_index("ix_user_events_product_id", "user_events", ["product_id"])
    op.create_index("ix_user_events_session_id", "user_events", ["session_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="heuristic"),
        sa.Column("model_version", sa.String(length=50), nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"])
    op.create_index("ix_recommendations_product_id", "recommendations", ["product_id"])
    op.create_index("ix_recommendations_created_at", "recommendations", ["created_at"])


def downgrade() -> None:
    op.drop_table("recommendations")
    op.drop_table("user_events")
    op.drop_table("products")
    op.drop_table("users")
