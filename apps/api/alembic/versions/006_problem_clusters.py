"""add problem_clusters and occurrence.cluster_id

Revision ID: 006_problem_clusters
Revises: 005_create_action_events
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_problem_clusters"
down_revision: str | None = "005_create_action_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "problem_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_title", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column(
            "normalized_key",
            sa.Text(),
            nullable=False,
            comment="Lowercased normalized_statement used for exact auto-link before embeddings",
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
    op.create_index(
        "ix_problem_clusters_user_id_normalized_key",
        "problem_clusters",
        ["user_id", "normalized_key"],
        unique=True,
    )

    op.add_column(
        "problem_occurrences",
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_problem_occurrences_cluster_id",
        "problem_occurrences",
        "problem_clusters",
        ["cluster_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_problem_occurrences_cluster_id",
        "problem_occurrences",
        ["cluster_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_problem_occurrences_cluster_id", table_name="problem_occurrences")
    op.drop_constraint(
        "fk_problem_occurrences_cluster_id",
        "problem_occurrences",
        type_="foreignkey",
    )
    op.drop_column("problem_occurrences", "cluster_id")
    op.drop_index(
        "ix_problem_clusters_user_id_normalized_key",
        table_name="problem_clusters",
    )
    op.drop_table("problem_clusters")
