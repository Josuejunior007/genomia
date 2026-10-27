from fastapi import APIRouter
from app.core.config import settings
from app.db.session import engine
from app.schemas.schema import SchemaSnapshot
from app.services.schema_service import SchemaService

router = APIRouter()


@router.get("", response_model=SchemaSnapshot, summary="Inspecionar estrutura do banco")
def get_schema() -> SchemaSnapshot:
    return SchemaService(engine, settings.db_schema).snapshot()
