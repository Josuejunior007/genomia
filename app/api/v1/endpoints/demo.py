from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.app_session import get_app_db
from app.models.suggestion import Suggestion
from app.schemas.schema import ReviewItem, ReviewRequest, ReviewResponse, SuggestionCreate

router = APIRouter()


def _response(item: Suggestion) -> ReviewItem:
    return ReviewItem(
        id=item.id, table=item.table_name, kind=item.kind,
        description=item.description, confidence=item.confidence,
        status=item.status, rationale=item.rationale,
    )


@router.get("/suggestions", response_model=list[ReviewItem], summary="Listar sugestões para revisão")
def list_suggestions(
    status: str = Query(default="pending", pattern="^(pending|approved|rejected|all)$"),
    db: Session = Depends(get_app_db),
):
    statement = select(Suggestion).order_by(Suggestion.created_at.desc(), Suggestion.id.desc())
    if status != "all":
        statement = statement.where(Suggestion.status == status)
    return [_response(item) for item in db.scalars(statement).all()]


@router.post("/suggestions", response_model=ReviewItem, status_code=201, summary="Registrar sugestão para revisão")
def create_suggestion(body: SuggestionCreate, db: Session = Depends(get_app_db)):
    item = Suggestion(
        table_name=body.table, kind=body.kind, description=body.description,
        confidence=body.confidence, rationale=body.rationale,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _response(item)


@router.post("/suggestions/{suggestion_id}/review", response_model=ReviewResponse, summary="Aprovar ou rejeitar sugestão")
def review_suggestion(suggestion_id: int, body: ReviewRequest, db: Session = Depends(get_app_db)):
    result = db.execute(
        update(Suggestion)
        .where(Suggestion.id == suggestion_id, Suggestion.status == "pending")
        .values(status=body.decision, review_comment=body.comment, reviewed_at=datetime.now(timezone.utc))
    )
    if result.rowcount == 0:
        exists = db.scalar(select(Suggestion.id).where(Suggestion.id == suggestion_id))
        if exists is None:
            raise HTTPException(status_code=404, detail="Sugestão não encontrada.")
        raise HTTPException(status_code=409, detail="Esta sugestão já foi revisada.")
    db.commit()
    return ReviewResponse(id=suggestion_id, status=body.decision, comment=body.comment)
