from fastapi import APIRouter
from app.api.v1.endpoints import advisor, relationships, schema, catalog, demo, dashboard,standardization

api_router = APIRouter()
api_router.include_router(schema.router, prefix="/schema", tags=["schema"])
api_router.include_router(advisor.router, prefix="/advisor", tags=["advisor"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(demo.router, tags=["governance-demo"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(relationships.router, prefix="/relationships", tags=["relationships"])
api_router.include_router(standardization.router, prefix="/standards", tags=["standards"])
