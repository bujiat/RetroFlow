import logging
from uuid import UUID

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.content_chunk import ContentChunk
from app.providers import embedding as embedding_provider
from app.repositories import chunks as chunks_repo

jieba.setLogLevel(logging.ERROR)
jieba.add_word("部署")
jieba.add_word("回滚")


def tokenize(text: str) -> list[str]:
    """Split Chinese and English text into BM25 terms. Drop punctuation and single characters."""
    tokens: list[str] = []
    for raw in jieba.lcut(text):
        token = raw.strip().lower()
        if len(token) < 2:
            continue
        if not any(char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in token):
            continue
        tokens.append(token)
    return tokens


def rank_bm25(query: str, chunks: list[ContentChunk], limit: int) -> list[ContentChunk]:
    """Highest BM25 scores first. Chunks with no tokens, and zero scores, are left out."""
    query_tokens = tokenize(query)
    usable = [(chunk, tokenize(chunk.content)) for chunk in chunks]
    usable = [(chunk, tokens) for chunk, tokens in usable if tokens]
    if not query_tokens or not usable or limit < 1:
        return []
    model = BM25Okapi([tokens for _, tokens in usable])
    # rank-bm25 gives IDF 0 when a term appears in exactly half the chunks
    # (two chunks, the word is in one of them). Floor those weights so the
    # matching chunk still outranks the chunk that lacks the word.
    for word, weight in model.idf.items():
        if weight <= 0:
            model.idf[word] = 0.25
    scores = model.get_scores(query_tokens)
    ranked = sorted(
        (
            (float(score), str(chunk.id), chunk)
            for score, (chunk, _) in zip(scores, usable, strict=True)
            if float(score) > 0
        ),
        key=lambda item: (-item[0], item[1]),
    )
    return [chunk for _, _, chunk in ranked[:limit]]


def rrf_fuse(
    rankings: list[list[ContentChunk]],
    *,
    k: int,
) -> list[tuple[ContentChunk, float]]:
    """Merge ranked lists. rank starts at 1. score = sum 1 / (k + rank)."""
    totals: dict[UUID, float] = {}
    chosen: dict[UUID, ContentChunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            chosen[chunk.id] = chunk
            totals[chunk.id] = totals.get(chunk.id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(totals.items(), key=lambda item: (-item[1], str(item[0])))
    return [(chosen[chunk_id], score) for chunk_id, score in ordered]


def retrieve_chunks(
    db: Session,
    *,
    user_id: UUID,
    query: str,
) -> list[tuple[ContentChunk, float]]:
    """Vector mode keeps the cosine threshold. Hybrid fuses that list with this user's BM25."""
    vector = embedding_provider.embed_texts([query])[0]
    vector_hits = chunks_repo.search_chunks(
        db,
        user_id=user_id,
        vector=vector,
        limit=settings.rag_retrieval_top_k,
    )
    if settings.rag_mode == "vector":
        return _above_threshold(vector_hits)
    keyword_hits = rank_bm25(
        query,
        chunks_repo.list_chunks_for_user(db, user_id=user_id),
        settings.rag_retrieval_top_k,
    )
    if not keyword_hits:
        return _above_threshold(vector_hits)
    fused = rrf_fuse(
        [[chunk for chunk, _score in vector_hits], keyword_hits],
        k=settings.rag_rrf_k,
    )
    return fused[: settings.rag_context_top_k]


def _above_threshold(
    scored: list[tuple[ContentChunk, float]],
) -> list[tuple[ContentChunk, float]]:
    kept = [(chunk, score) for chunk, score in scored if score >= settings.rag_min_score]
    return kept[: settings.rag_context_top_k]
