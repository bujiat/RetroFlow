from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.repositories.chunks import chunks_for_user_statement
from app.retrieval.search import rank_bm25, retrieve_chunks, tokenize


def _chunk(content: str, user_id=None):
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id or uuid4(),
        retro_id=uuid4(),
        content=content,
    )


def test_tokenize_keeps_deploy_and_rollback_terms() -> None:
    assert "部署" in tokenize("这次部署失败，端口写错了")
    assert "回滚" in tokenize("故障后执行回滚，切回旧版本")


def test_chunks_query_is_limited_to_one_user() -> None:
    user_id = uuid4()
    statement = chunks_for_user_statement(user_id)
    sql = str(statement)
    params = statement.compile().params
    assert "content_chunks.user_id" in sql
    assert user_id in params.values()


def test_keyword_hits_beat_vector_only(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    deploy = _chunk("上线前没有核对配置，部署失败后才发现端口写错", user_id)
    rollback = _chunk("故障时按手册执行回滚，流量切回旧版本", user_id)
    chatter = _chunk("本周站会主要同步了请假和团建安排", user_id)
    outsider = _chunk("别人的复盘里也写了回滚步骤", uuid4())
    owned = [deploy, rollback, chatter]

    def fake_search(db, *, user_id, vector, limit):
        assert outsider not in owned
        return [(chatter, 0.91), (deploy, 0.20), (rollback, 0.05)]

    monkeypatch.setattr("app.retrieval.search.embedding_provider.embed_texts", lambda _texts: [[0.0]])
    monkeypatch.setattr("app.retrieval.search.chunks_repo.search_chunks", fake_search)
    monkeypatch.setattr(
        "app.retrieval.search.chunks_repo.list_chunks_for_user",
        lambda db, *, user_id: owned,
    )
    monkeypatch.setattr(settings, "rag_min_score", 0.32)
    monkeypatch.setattr(settings, "rag_context_top_k", 2)
    monkeypatch.setattr(settings, "rag_retrieval_top_k", 10)
    monkeypatch.setattr(settings, "rag_rrf_k", 60)

    monkeypatch.setattr(settings, "rag_mode", "vector")
    vector_hits = retrieve_chunks(None, user_id=user_id, query="回滚")  # type: ignore[arg-type]
    assert [chunk.id for chunk, _score in vector_hits] == [chatter.id]

    monkeypatch.setattr(settings, "rag_mode", "hybrid")
    rollback_hits = retrieve_chunks(None, user_id=user_id, query="回滚")  # type: ignore[arg-type]
    deploy_hits = retrieve_chunks(None, user_id=user_id, query="部署")  # type: ignore[arg-type]
    assert rollback_hits[0][0].id == rollback.id
    assert deploy_hits[0][0].id == deploy.id
    assert outsider.id not in {chunk.id for chunk, _score in rollback_hits}


def test_vector_mode_does_not_load_the_keyword_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_list(db, *, user_id):
        raise AssertionError("vector mode must not scan every chunk")

    monkeypatch.setattr(settings, "rag_mode", "vector")
    monkeypatch.setattr(
        "app.retrieval.search.embedding_provider.embed_texts",
        lambda _texts: [[0.1]],
    )
    monkeypatch.setattr(
        "app.retrieval.search.chunks_repo.search_chunks",
        lambda db, *, user_id, vector, limit: [],
    )
    monkeypatch.setattr("app.retrieval.search.chunks_repo.list_chunks_for_user", fail_list)
    assert retrieve_chunks(None, user_id=uuid4(), query="回滚") == []  # type: ignore[arg-type]


def test_bm25_finds_a_rare_term_among_two_chunks() -> None:
    mine = _chunk("发布后执行回滚")
    other = _chunk("本周只讨论了团建")
    ranked = rank_bm25("回滚", [mine, other], limit=5)
    assert [chunk.id for chunk in ranked] == [mine.id]


def test_unknown_rag_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://localhost/retroflow", rag_mode="bm25")
