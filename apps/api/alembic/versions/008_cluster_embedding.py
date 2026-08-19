"""add problem_clusters.representative_embedding

Revision ID: 008_cluster_embedding
Revises: 007_drop_cluster_normalized_key
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_cluster_embedding"
down_revision: str | None = "007_drop_cluster_normalized_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "problem_clusters",
        sa.Column(
            "representative_embedding",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("problem_clusters", "representative_embedding")
