from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.permissions import validate_read_only
from app.db.session import Base, engine
from app.models.suggestion import Suggestion


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "MVP demonstrativo do GenomAI: catálogo, análise determinística "
        "e revisão humana. Sugestões nunca são executadas automaticamente."
    ),
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
def enforce_read_only_database_role() -> None:
    """Não inicia a API se o usuário do banco tiver permissão de escrita."""
    validate_read_only(engine, settings.db_schema)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    """Converte erros do banco em uma resposta HTTP 503."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "API ativa, mas o banco de dados está indisponível. "
                "Tente novamente mais tarde."
            ),
            "code": "database_unavailable",
        },
    )


@app.get("/", tags=["health"])
def root():
    return {
        "name": settings.app_name,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
            "engine": "PostgreSQL",
        }

    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "API ativa, mas o banco de dados está indisponível. "
                    "Tente novamente mais tarde."
                ),
                "code": "database_unavailable",
            },
        )