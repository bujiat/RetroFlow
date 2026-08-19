"""create action_items table

Revision ID: 004_create_action_items
Revises: 003_analysis_tables
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_create_action_items"
down_revision: str | None = "003_analysis_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retro_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("problem_occurrence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=320), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("success_criteria", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["retro_id"], ["retros.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["problem_occurrence_id"],
            ["problem_occurrences.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_action_items_user_id_status", "action_items", ["user_id", "status"])
    op.create_index("ix_action_items_user_id_due_date", "action_items", ["user_id", "due_date"])
    op.create_index(
        "ix_action_items_problem_occurrence_id",
        "action_items",
        ["problem_occurrence_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_items_problem_occurrence_id", table_name="action_items")
    op.drop_index("ix_action_items_user_id_due_date", table_name="action_items")
    op.drop_index("ix_action_items_user_id_status", table_name="action_items")
    op.drop_table("action_items")
