"""Index retro raw_content into content_chunks for RAG."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.retro import Retro
from app.providers import embedding as embedding_provider
from app.repositories import chunks as chunks_repo


def index_retro_content(db: Session, *, user_id: UUID, retro: Retro) -> None:
    """Replace chunks for one retro and set index_status.

    Embedding failures set index_status=failed and do not raise — callers that
    must not fail the parent transaction can rely on that. Re-raises only for
    unexpected errors after marking failed when appropriate.
    """
    try:
        chunks_repo.replace_chunks_for_retro(db, user_id=user_id, retro=retro)
        retro.index_status = "ready"
    except embedding_provider.EmbeddingError:
        chunks_repo.delete_chunks_for_retro(db, user_id=user_id, retro_id=retro.id)
        retro.index_status = "failed"
