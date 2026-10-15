from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.db.session import engine
from app.schemas.schema import TableInfo
from app.services.schema_service import SchemaService

router = APIRouter()

@router.get("/tables", summary="Listar tabelas do catálogo")
def list_tables(q: str | None = Query(default=None, max_length=80)):
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
        tables = snapshot.tables
        if q and q.strip():
            term = q.strip().casefold()
            tables = [t for t in tables if term in t.name.casefold()
                      or any(term in c.name.casefold() for c in t.columns)]
        return {"count": len(tables), "items": [
            {"name": t.name, "schema": t.schema, "columns_count": len(t.columns),
             "primary_key": t.primary_key, "foreign_keys_count": len(t.foreign_keys)}
            for t in tables
        ]}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Catálogo indisponível; verifique a conexão com o banco.")

@router.get("/tables/{table_name}", response_model=TableInfo, summary="Detalhar tabela")
def get_table(table_name: str):
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
        for table in snapshot.tables:
            if table.name == table_name:
                return table
        raise HTTPException(status_code=404, detail="Tabela não encontrada no schema configurado.")
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Catálogo indisponível; verifique a conexão com o banco.")
