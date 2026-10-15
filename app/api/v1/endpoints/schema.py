from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.db.session import engine
from app.schemas.schema import SchemaSnapshot
from app.services.schema_service import SchemaService

router = APIRouter()

@router.get("", response_model=SchemaSnapshot, summary="Inspecionar estrutura do banco")
def get_schema() -> SchemaSnapshot:
    try:
        return SchemaService(engine, settings.db_schema).snapshot()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Não foi possível ler os metadados do banco. Verifique a conexão e o schema.")
