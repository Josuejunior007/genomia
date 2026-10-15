from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.db.session import engine
from app.services.schema_service import SchemaService
from app.api.v1.endpoints.demo import suggestions

router = APIRouter()

@router.get("/metrics", summary="Indicadores de governança")
def metrics():
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Métricas indisponíveis; verifique a conexão com o banco.")
    total = len(snapshot.tables)
    documented = sum(1 for t in snapshot.tables if t.name.startswith("app") and t.columns)
    pending = sum(1 for s in suggestions if s["status"] == "pending")
    return {
        "tables_total": total,
        "tables_with_basic_metadata": documented,
        "metadata_coverage_percent": round(documented / total * 100, 1) if total else 0,
        "tables_without_primary_key": sum(1 for t in snapshot.tables if not t.primary_key),
        "pending_demo_suggestions": pending,
        "note": "Cobertura considera metadados básicos, não documentação de negócio aprovada. Sugestões são demonstrativas."
    }
