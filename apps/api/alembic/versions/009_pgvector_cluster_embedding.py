"""enable pgvector; store cluster embeddings as vector + HNSW

Revision ID: 009_pgvector_cluster
Revises: 008_cluster_embedding
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op

# Must match Settings.embedding_dim / nomic-embed-text
EMBEDDING_DIM = 768

revision: str = "009_pgvector_cluster"
down_revision: str | None = "008_cluster_embedding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        f"""
        ALTER TABLE problem_clusters
        ALTER COLUMN representative_embedding
        TYPE vector({EMBEDDING_DIM})
        USING (
            CASE
                WHEN representative_embedding IS NULL THEN NULL
                ELSE representative_embedding::text::vector
            END
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_problem_clusters_embedding_hnsw
        ON problem_clusters
        USING hnsw (representative_embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_problem_clusters_embedding_hnsw")
    op.execute(
        """
        ALTER TABLE problem_clusters
        ALTER COLUMN representative_embedding
        TYPE jsonb
        USING (
            CASE
                WHEN representative_embedding IS NULL THEN NULL
                ELSE to_jsonb(representative_embedding::real[])
            END
        )
        """
    )
