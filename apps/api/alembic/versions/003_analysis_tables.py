"""add analysis summary + problem_occurrences + action_drafts

Revision ID: 003_analysis_tables
Revises: 002_create_retros
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_analysis_tables"
down_revision: str | None = "002_create_retros"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "retros",
        sa.Column("analysis_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "problem_occurrences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retro_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("normalized_statement", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("source_quote", sa.Text(), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False, server_default="kept"),
        sa.Column("match_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retro_id"], ["retros.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_problem_occurrences_retro_id",
        "problem_occurrences",
        ["retro_id"],
    )
    op.create_index(
        "ix_problem_occurrences_user_id_retro_id",
        "problem_occurrences",
        ["user_id", "retro_id"],
    )

    op.create_table(
        "action_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retro_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("problem_occurrence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("suggested_success_criteria", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
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
    op.create_index("ix_action_drafts_retro_id", "action_drafts", ["retro_id"])
    op.create_index(
        "ix_action_drafts_problem_occurrence_id",
        "action_drafts",
        ["problem_occurrence_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_drafts_problem_occurrence_id", table_name="action_drafts")
    op.drop_index("ix_action_drafts_retro_id", table_name="action_drafts")
    op.drop_table("action_drafts")
    op.drop_index("ix_problem_occurrences_user_id_retro_id", table_name="problem_occurrences")
    op.drop_index("ix_problem_occurrences_retro_id", table_name="problem_occurrences")
    op.drop_table("problem_occurrences")
    op.drop_column("retros", "analysis_summary")
