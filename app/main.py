from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="MVP demonstrativo do GenomAI: catálogo, análise determinística e revisão humana. Sugestões nunca são executadas automaticamente."
)
app.include_router(api_router, prefix="/api/v1")

@app.get("/", tags=["health"])
def root():
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}

@app.get("/health", tags=["health"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected", "engine": "PostgreSQL"}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="API ativa, mas o banco de dados está indisponível.")
