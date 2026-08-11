"""add recommendation_batches table and recommendations.batch_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("interest_summary", sa.Text(), nullable=True),
        sa.Column("trigger_source", sa.String(length=30), nullable=False, server_default="on_demand"),
        sa.Column("confidence", sa.String(length=20), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recommendation_batches_user_id", "recommendation_batches", ["user_id"])
    op.create_index("ix_recommendation_batches_created_at", "recommendation_batches", ["created_at"])

    op.add_column(
        "recommendations",
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("recommendation_batches.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_recommendations_batch_id", "recommendations", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_recommendations_batch_id", table_name="recommendations")
    op.drop_column("recommendations", "batch_id")
    op.drop_index("ix_recommendation_batches_created_at", table_name="recommendation_batches")
    op.drop_index("ix_recommendation_batches_user_id", table_name="recommendation_batches")
    op.drop_table("recommendation_batches")
