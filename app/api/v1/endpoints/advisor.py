from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.db.session import engine
from app.schemas.schema import AnalysisReport
from app.services.advisor_service import AdvisorService
from app.services.schema_service import SchemaService

router = APIRouter()

@router.get("/analyze", response_model=AnalysisReport, summary="Analisar qualidade estrutural")
def analyze_schema() -> AnalysisReport:
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
        return AdvisorService().analyze(snapshot)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Análise indisponível: não foi possível consultar os metadados do banco.")
