
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import engine, get_db
from app.models.suggestion import Suggestion
from app.services.schema_service import SchemaService

router = APIRouter()


@router.get("/metrics", summary="Indicadores de governança")
def metrics(db: Session = Depends(get_db)):
    try:
        snapshot = SchemaService(
            engine, settings.db_schema
        ).snapshot()

        total_suggestions = db.scalar(
            select(func.count()).select_from(Suggestion)
        ) or 0

        pending = db.scalar(
            select(func.count())
            .select_from(Suggestion)
            .where(Suggestion.status == "pending")
        ) or 0

        approved = db.scalar(
            select(func.count())
            .select_from(Suggestion)
            .where(Suggestion.status == "approved")
        ) or 0

        rejected = db.scalar(
            select(func.count())
            .select_from(Suggestion)
            .where(Suggestion.status == "rejected")
        ) or 0

        reviewed = approved + rejected

        review_rate = round(
            reviewed / total_suggestions * 100, 1
        ) if total_suggestions else 0

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Métricas indisponíveis; verifique "
                "a conexão com o banco."
            ),
        )

    total = len(snapshot.tables)

    tables_with_metadata = sum(
        1 for table in snapshot.tables
        if table.columns
    )

    return {
        "tables_total": total,
        "tables_with_basic_metadata": tables_with_metadata,
        "metadata_coverage_percent": round(
            tables_with_metadata / total * 100, 1
        ) if total else 0,
        "tables_without_primary_key": sum(
            1 for table in snapshot.tables
            if not table.primary_key
        ),
        "pending_suggestions": pending,
        "total_suggestions": total_suggestions,
        "approved_suggestions": approved,
        "rejected_suggestions": rejected,
        "reviewed_suggestions": reviewed,
        "review_rate_percent": review_rate,
        "note": (
            "A cobertura representa tabelas com colunas identificadas, "
            "não documentação de negócio aprovada."
        ),
    }
