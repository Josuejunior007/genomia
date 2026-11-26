"""Rotas do catálogo: tabelas, registros e relacionamentos.

Todas as rotas são de leitura e usam ``SchemaService``/``TableDataService``,
que excluem as tabelas internas do GenomAI antes de expor qualquer informação.
"""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import engine
from app.schemas.schema import TableInfo, TableRelationships, TableRows
from app.services.schema_service import SchemaService
from app.services.table_data_service import TableDataService, TableNotFoundError

router = APIRouter()


@router.get("/tables", summary="Listar tabelas do catálogo")
def list_tables(q: str | None = Query(default=None, max_length=80)):
    """Lista tabelas e permite busca por nome de tabela ou coluna."""
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
        tables = snapshot.tables
        if q and q.strip():
            term = q.strip().casefold()
            tables = [
                table
                for table in tables
                if term in table.name.casefold()
                or any(term in column.name.casefold() for column in table.columns)
            ]
        return {
            "count": len(tables),
            "items": [
                {
                    "name": table.name,
                    "schema": table.schema,
                    "columns_count": len(table.columns),
                    "primary_key": table.primary_key,
                    "foreign_keys_count": len(table.foreign_keys),
                }
                for table in tables
            ],
        }
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Catálogo indisponível; verifique a conexão com o banco.",
        )


@router.get("/tables/{table_name}", response_model=TableInfo, summary="Detalhar tabela")
def get_table(table_name: str):
    """Retorna colunas, chaves e índices de uma tabela do schema analisado."""
    try:
        table = SchemaService(engine, settings.db_schema).table(table_name)
        if table is None:
            raise HTTPException(
                status_code=404,
                detail="Tabela não encontrada no schema configurado.",
            )
        return table
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Catálogo indisponível; verifique a conexão com o banco.",
        )


@router.get(
    "/tables/{table_name}/rows",
    response_model=TableRows,
    summary="Consultar registros da tabela",
)
def get_table_rows(
    table_name: str,
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Pagina registros em modo somente leitura.

    Esses valores são exibidos na interface de exploração e **nunca** são
    enviados ao provedor de IA.
    """
    try:
        return TableDataService(engine, settings.db_schema).rows(
            table_name, limit, offset
        )
    except TableNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Tabela não encontrada no schema configurado.",
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Não foi possível ler os dados desta tabela."
        )


@router.get(
    "/tables/{table_name}/relationships",
    response_model=TableRelationships,
    summary="Consultar relacionamentos da tabela",
)
def get_table_relationships(table_name: str):
    """Lista as chaves estrangeiras de saída e de entrada desta tabela."""
    try:
        return TableDataService(engine, settings.db_schema).relationships(table_name)
    except TableNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Tabela não encontrada no schema configurado.",
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível ler os relacionamentos desta tabela.",
        )
