import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.app_session import get_app_db
from app.db.session import engine
from app.models.suggestion import Suggestion
from app.schemas.schema import AnalysisReport
from app.services.advisor_service import AdvisorService
from app.services.gemini_advisor_service import GeminiAdvisorService
from app.services.schema_service import SchemaService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/analyze", response_model=AnalysisReport, summary="Analisar qualidade estrutural")
def analyze_schema() -> AnalysisReport:
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
        return AdvisorService().analyze(snapshot)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Análise indisponível: não foi possível consultar os metadados do banco.")


@router.post("/ai-analyze", summary="Analisar esquema com Gemini e salvar propostas para revisão")
def analyze_schema_with_ai(db: Session = Depends(get_app_db)):
    if not settings.ai_enabled:
        raise HTTPException(status_code=503, detail="Análise com IA desativada. Configure AI_ENABLED=true.")
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Configure GEMINI_API_KEY no ambiente da API.")
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Análise indisponível: não foi possível consultar os metadados do banco.")

    try:
        deterministic = AdvisorService().analyze(snapshot)
        analysis = GeminiAdvisorService(settings.gemini_api_key, settings.gemini_model).analyze(snapshot, deterministic)
    except Exception as exc:
        logger.exception("Falha ao consultar o Gemini")
        raise HTTPException(status_code=502, detail="O serviço Gemini não conseguiu concluir a análise. Verifique a chave, o modelo e os limites da API.") from exc

    tables = {table.name for table in snapshot.tables}
    created = []
    for proposal in analysis.suggestions:
        # Model output is untrusted: only attach proposals to tables in this snapshot.
        if proposal.table not in tables:
            continue
        candidate_sql = proposal.suggested_sql.strip()
        if candidate_sql and not candidate_sql.upper().startswith(("CREATE INDEX ", "CREATE UNIQUE INDEX ", "COMMENT ON ")):
            candidate_sql = ""
        rationale = f"Evidência: {proposal.evidence}\n\nRiscos e incertezas: {proposal.risks_and_uncertainty}"
        if candidate_sql:
            rationale += f"\n\nSQL candidato (não executado): {candidate_sql}"
        item = Suggestion(
            table_name=proposal.table,
            kind=proposal.kind[:40],
            description=proposal.description[:5000],
            confidence=proposal.confidence,
            rationale=rationale[:5000],
        )
        db.add(item)
        created.append(item)
    try:
        db.commit()
        for item in created:
            db.refresh(item)
    except SQLAlchemyError:
        db.rollback()
        raise
    return {
        "summary": analysis.summary,
        "suggestions_created": len(created),
        "suggestions": [
            {"id": item.id, "table": item.table_name, "kind": item.kind,
             "description": item.description, "confidence": item.confidence,
             "status": item.status, "rationale": item.rationale}
            for item in created
        ],
        "human_review_required": True,
        "database_changes_applied": False,
    }
