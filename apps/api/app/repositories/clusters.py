from uuid import UUID, uuid4

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.problem import ProblemOccurrence
from app.models.problem_cluster import ProblemCluster
from app.providers import embedding as embedding_provider


def get_cluster_for_user(
    db: Session,
    *,
    user_id: UUID,
    cluster_id: UUID,
) -> ProblemCluster | None:
    return db.scalars(
        select(ProblemCluster).where(
            ProblemCluster.user_id == user_id,
            ProblemCluster.id == cluster_id,
        )
    ).first()


def list_clusters_for_user(db: Session, user_id: UUID) -> list[tuple[ProblemCluster, int]]:
    stmt = (
        select(ProblemCluster, func.count(ProblemOccurrence.id))
        .outerjoin(
            ProblemOccurrence,
            (ProblemOccurrence.cluster_id == ProblemCluster.id)
            & (ProblemOccurrence.disposition == "kept"),
        )
        .where(ProblemCluster.user_id == user_id)
        .group_by(ProblemCluster.id)
        .order_by(func.count(ProblemOccurrence.id).desc(), ProblemCluster.updated_at.desc())
    )
    return list(db.execute(stmt).all())


def create_cluster(
    db: Session,
    *,
    user_id: UUID,
    title: str,
    category: str,
    representative_embedding: list[float] | None = None,
) -> ProblemCluster:
    if representative_embedding is not None:
        _ensure_dim(representative_embedding)
    cluster = ProblemCluster(
        id=uuid4(),
        user_id=user_id,
        canonical_title=title.strip(),
        category=category,
        representative_embedding=representative_embedding,
    )
    db.add(cluster)
    db.flush()
    return cluster


def _ensure_dim(vector: list[float]) -> None:
    if len(vector) != settings.embedding_dim:
        raise embedding_provider.EmbeddingError("embedding_dim_mismatch")


def _has_kept_occurrence():
    return exists(
        select(ProblemOccurrence.id).where(
            ProblemOccurrence.cluster_id == ProblemCluster.id,
            ProblemOccurrence.disposition == "kept",
        )
    )


def find_nearest_cluster(
    db: Session,
    *,
    user_id: UUID,
    vector: list[float],
) -> tuple[ProblemCluster, float] | None:
    """Return (cluster, cosine_similarity) for the nearest active cluster, if any.

    Uses pgvector cosine distance (`<=>` / .cosine_distance). Similarity = 1 - distance.
    """
    _ensure_dim(vector)
    distance = ProblemCluster.representative_embedding.cosine_distance(vector)
    row = db.execute(
        select(ProblemCluster, distance.label("distance"))
        .where(
            ProblemCluster.user_id == user_id,
            ProblemCluster.representative_embedding.is_not(None),
            _has_kept_occurrence(),
        )
        .order_by(distance)
        .limit(1)
    ).first()
    if row is None:
        return None
    cluster, dist = row
    return cluster, 1.0 - float(dist)


def _embed_text(problem: ProblemOccurrence) -> str:
    return f"{problem.title}\n{problem.normalized_statement}"


def assign_clusters_for_problems(
    db: Session,
    *,
    user_id: UUID,
    problems: list[ProblemOccurrence],
) -> None:
    """Embed each occurrence and link to a similar cluster, or create one.

    Nearest-cluster search runs in PostgreSQL via pgvector (HNSW + cosine).
    Failures raise EmbeddingError (caller should fail the analyze).
    """
    if not problems:
        return

    vectors = embedding_provider.embed_texts([_embed_text(p) for p in problems])
    threshold = settings.problem_match_threshold

    for problem, vector in zip(problems, vectors, strict=True):
        _ensure_dim(vector)
        nearest = find_nearest_cluster(db, user_id=user_id, vector=vector)

        if nearest is not None and nearest[1] >= threshold:
            problem.cluster_id = nearest[0].id
            problem.match_status = "auto_linked"
            # Flush so the next problem in this batch can see this kept link in SQL.
            db.flush()
            continue

        cluster = create_cluster(
            db,
            user_id=user_id,
            title=problem.title,
            category=problem.category,
            representative_embedding=vector,
        )
        problem.cluster_id = cluster.id
        problem.match_status = "auto_created"
        db.flush()


def get_occurrence_for_user(
    db: Session,
    *,
    user_id: UUID,
    occurrence_id: UUID,
) -> ProblemOccurrence | None:
    return db.scalars(
        select(ProblemOccurrence).where(
            ProblemOccurrence.user_id == user_id,
            ProblemOccurrence.id == occurrence_id,
        )
    ).first()


def clusters_by_ids(
    db: Session,
    *,
    user_id: UUID,
    cluster_ids: list[UUID],
) -> dict[UUID, ProblemCluster]:
    if not cluster_ids:
        return {}
    rows = db.scalars(
        select(ProblemCluster).where(
            ProblemCluster.user_id == user_id,
            ProblemCluster.id.in_(cluster_ids),
        )
    ).all()
    return {row.id: row for row in rows}
