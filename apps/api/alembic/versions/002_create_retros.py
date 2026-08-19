"""create retros table

Revision ID: 002_create_retros
Revises: 001_create_users
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_create_retros"
down_revision: str | None = "001_create_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retros",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("index_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_retros_user_id_created_at", "retros", ["user_id", "created_at"])
    op.create_index("ix_retros_user_id_status", "retros", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_retros_user_id_status", table_name="retros")
    op.drop_index("ix_retros_user_id_created_at", table_name="retros")
    op.drop_table("retros")
