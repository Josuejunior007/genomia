"""Ponto de entrada da API GenomAI.

A aplicação sobe com três garantias verificadas no startup:

1. o banco analisado usa uma role PostgreSQL somente leitura;
2. o armazenamento interno existe (schema/tabelas) e está isolado;
3. a configuração de escrita é opcional e explícita (``DB_WRITE_ENABLED``).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.app_session import ensure_app_store, validate_store_isolation
from app.db.permissions import validate_read_only
from app.db.session import engine

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description=(
        "GenomAI: catálogo, análise estrutural, revisão humana por personas e "
        "documentação. Sugestões nunca são executadas automaticamente; a IA "
        "recebe apenas metadados seguros."
    ),
)
app.include_router(api_router, prefix="/api/v1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-GenomAI-Persona"],
)


@app.on_event("startup")
def startup_checks() -> None:
    """Valida permissões, prepara o banco interno e confere o isolamento."""
    ensure_app_store()
    validate_read_only(engine, settings.db_schema)
    for warning in validate_store_isolation(engine):
        logger.warning("Isolamento de armazenamento: %s", warning)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Converte falhas de conexão, timeout e outras falhas SQLAlchemy em 503."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": "API ativa, mas o banco de dados está indisponível. Tente novamente mais tarde.",
            "code": "database_unavailable",
        },
    )


@app.get("/", tags=["health"])
def root():
    """Identifica a API e aponta para o Swagger."""
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}


@app.get("/health", tags=["health"])
def health():
    """Confirma que a API consegue acessar o banco analisado."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected", "engine": "PostgreSQL"}
