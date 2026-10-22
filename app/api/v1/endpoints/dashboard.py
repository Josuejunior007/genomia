from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.endpoints.demo import suggestions
from app.core.config import settings
from app.db.session import engine
from app.services.schema_service import SchemaService

router = APIRouter()


@router.get("/metrics", summary="Indicadores de governança")
def metrics():
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Métricas indisponíveis; verifique a conexão com o banco.",
        )

    total = len(snapshot.tables)
    # This is metadata coverage, not approved business documentation coverage.
    with_basic_metadata = sum(1 for table in snapshot.tables if table.columns)
    pending = sum(1 for suggestion in suggestions if suggestion["status"] == "pending")

    return {
        "tables_total": total,
        "tables_with_basic_metadata": with_basic_metadata,
        "metadata_coverage_percent": round(with_basic_metadata / total * 100, 1) if total else 0,
        "tables_without_primary_key": sum(1 for table in snapshot.tables if not table.primary_key),
        "pending_demo_suggestions": pending,
        "note": (
            "Cobertura considera tabelas com metadados de colunas, não documentação "
            "de negócio aprovada. Sugestões são demonstrativas."
        ),
    }
