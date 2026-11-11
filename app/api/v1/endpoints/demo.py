
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.suggestion import Suggestion
from app.schemas.schema import ReviewItem, ReviewRequest, ReviewResponse

router = APIRouter()


@router.get(
    "/suggestions",
    response_model=list[ReviewItem],
    summary="Listar sugestões para revisão humana",
)
def list_suggestions(
    status: str = "pending",
    db: Session = Depends(get_db),
):
    if status not in {"pending", "approved", "rejected", "all"}:
        raise HTTPException(
            status_code=400,
            detail="Filtro inválido. Use pending, approved, rejected ou all.",
        )

    query = select(Suggestion).order_by(Suggestion.id)

    if status != "all":
        query = query.where(Suggestion.status == status)

    suggestions = db.scalars(query).all()

    return [
        {
            "id": item.id,
            "table": item.table_name,
            "kind": item.kind,
            "description": item.description,
            "confidence": item.confidence,
            "status": item.status,
            "rationale": item.rationale,
        }
        for item in suggestions
    ]


@router.post(
    "/suggestions/{suggestion_id}/review",
    response_model=ReviewResponse,
    summary="Aprovar ou rejeitar uma sugestão",
)
def review_suggestion(
    suggestion_id: int,
    body: ReviewRequest,
    db: Session = Depends(get_db),
):
    item = db.get(Suggestion, suggestion_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Sugestão não encontrada.",
        )

    if item.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Esta sugestão já foi revisada.",
        )

    item.status = body.decision
    item.review_comment = body.comment
    item.reviewed_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Não foi possível salvar a revisão no banco de dados.",
        )

    return ReviewResponse(
        id=item.id,
        status=item.status,
        comment=item.review_comment,
    )
