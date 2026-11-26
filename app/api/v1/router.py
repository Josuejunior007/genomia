"""Agregador das rotas versionadas da API."""

from fastapi import APIRouter

from app.api.v1.endpoints import advisor, catalog, dashboard, schema, suggestions, system

api_router = APIRouter()
api_router.include_router(schema.router, prefix="/schema", tags=["schema"])
api_router.include_router(advisor.router, prefix="/advisor", tags=["advisor"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(suggestions.router, tags=["governance"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(system.router, tags=["system"])
