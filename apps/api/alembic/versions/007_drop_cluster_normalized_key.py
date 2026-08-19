"""drop problem_clusters.normalized_key

Revision ID: 007_drop_cluster_normalized_key
Revises: 006_problem_clusters
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007_drop_cluster_normalized_key"
down_revision: str | None = "006_problem_clusters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ix_problem_clusters_user_id_normalized_key",
        table_name="problem_clusters",
    )
    op.drop_column("problem_clusters", "normalized_key")


def downgrade() -> None:
    op.add_column(
        "problem_clusters",
        sa.Column("normalized_key", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_problem_clusters_user_id_normalized_key",
        "problem_clusters",
        ["user_id", "normalized_key"],
        unique=True,
    )
    op.alter_column("problem_clusters", "normalized_key", server_default=None)
