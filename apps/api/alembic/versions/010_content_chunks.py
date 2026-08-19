"""content_chunks for RAG (pgvector)

Revision ID: 010_content_chunks
Revises: 009_pgvector_cluster
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op

EMBEDDING_DIM = 768

revision: str = "010_content_chunks"
down_revision: str | None = "009_pgvector_cluster"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        f"""
        CREATE TABLE content_chunks (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            retro_id UUID NOT NULL REFERENCES retros(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            start_offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            embedding vector({EMBEDDING_DIM}),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_content_chunks_retro_index UNIQUE (retro_id, chunk_index)
        )
        """
    )
    op.execute("CREATE INDEX ix_content_chunks_user_id ON content_chunks (user_id)")
    op.execute("CREATE INDEX ix_content_chunks_retro_id ON content_chunks (retro_id)")
    op.execute(
        """
        CREATE INDEX ix_content_chunks_embedding_hnsw
        ON content_chunks
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_content_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_content_chunks_retro_id")
    op.execute("DROP INDEX IF EXISTS ix_content_chunks_user_id")
    op.execute("DROP TABLE IF EXISTS content_chunks")
