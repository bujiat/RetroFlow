from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services import clusters as clusters_service
from app.services.clusters import ProblemClusterOut, RelinkOccurrenceRequest

router = APIRouter(prefix="/problems", tags=["problems"])


@router.get("/clusters", response_model=list[ProblemClusterOut])
def list_clusters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProblemClusterOut]:
    return clusters_service.list_clusters(db, current_user)


@router.patch(
    "/occurrences/{occurrence_id}/cluster",
    response_model=ProblemClusterOut,
)
def relink_occurrence(
    occurrence_id: UUID,
    payload: RelinkOccurrenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProblemClusterOut:
    return clusters_service.relink_occurrence(
        db,
        current_user,
        occurrence_id,
        payload,
    )
