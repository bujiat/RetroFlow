from uuid import UUID, uuid4

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.content_chunk import ContentChunk
from app.models.retro import Retro
from app.providers import embedding as embedding_provider

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=700,
    chunk_overlap=80,
    add_start_index=True,
    separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
)


def chunk_text(text: str) -> list[tuple[int, int, str]]:
    """Split text with RecursiveCharacterTextSplitter. Returns (start, end, content)."""
    cleaned = text.strip()
    if not cleaned:
        return []
    docs = _SPLITTER.create_documents([cleaned])
    pieces: list[tuple[int, int, str]] = []
    for doc in docs:
        content = doc.page_content.strip()
        if not content:
            continue
        start = int(doc.metadata.get("start_index", 0))
        pieces.append((start, start + len(content), content))
    return pieces


def delete_chunks_for_retro(db: Session, *, user_id: UUID, retro_id: UUID) -> None:
    db.execute(
        delete(ContentChunk).where(
            ContentChunk.user_id == user_id,
            ContentChunk.retro_id == retro_id,
        )
    )


def replace_chunks_for_retro(
    db: Session,
    *,
    user_id: UUID,
    retro: Retro,
) -> int:
    """Re-chunk retro.raw_content, embed, and replace stored chunks.

    Raises EmbeddingError on provider failure. Caller decides index_status.
    """
    delete_chunks_for_retro(db, user_id=user_id, retro_id=retro.id)
    db.flush()

    pieces = chunk_text(retro.raw_content)
    if not pieces:
        return 0

    vectors = embedding_provider.embed_texts([content for _, _, content in pieces])
    if len(vectors) != len(pieces):
        raise embedding_provider.EmbeddingError("embedding_bad_response")

    for index, ((start, end, content), vector) in enumerate(
        zip(pieces, vectors, strict=True)
    ):
        if len(vector) != settings.embedding_dim:
            raise embedding_provider.EmbeddingError("embedding_dim_mismatch")
        db.add(
            ContentChunk(
                id=uuid4(),
                user_id=user_id,
                retro_id=retro.id,
                chunk_index=index,
                content=content,
                start_offset=start,
                end_offset=end,
                embedding=vector,
            )
        )
    db.flush()
    return len(pieces)


def search_chunks(
    db: Session,
    *,
    user_id: UUID,
    vector: list[float],
    limit: int,
) -> list[tuple[ContentChunk, float]]:
    """Return (chunk, cosine_similarity) ordered by nearest first."""
    if len(vector) != settings.embedding_dim:
        raise embedding_provider.EmbeddingError("embedding_dim_mismatch")

    distance = ContentChunk.embedding.cosine_distance(vector)
    rows = db.execute(
        select(ContentChunk, distance.label("distance"))
        .where(
            ContentChunk.user_id == user_id,
            ContentChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(limit)
    ).all()
    return [(chunk, 1.0 - float(dist)) for chunk, dist in rows]
