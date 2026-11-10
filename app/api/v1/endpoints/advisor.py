import logging
import re
import unicodedata
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.app_session import get_app_db
from app.db.session import engine
from app.models.suggestion import Suggestion
from app.schemas.schema import AnalysisReport
from app.services.advisor_service import AdvisorService
from app.services.gemini_advisor_service import GeminiAdvisorService, GeminiSuggestion
from app.services.schema_service import SchemaService

router = APIRouter()
logger = logging.getLogger(__name__)


def _normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _is_duplicate(proposal: GeminiSuggestion, saved: list[tuple[str, str, str]]) -> bool:
    """Compare with persisted proposals so reruns do not refill the review queue."""
    table = _normalized_text(proposal.table)
    kind = _normalized_text(proposal.kind)
    description = _normalized_text(proposal.description)
    words = set(description.split())
    for saved_table, saved_kind, saved_description in saved:
        if table != saved_table:
            continue
        ratio = SequenceMatcher(None, description, saved_description).ratio()
        saved_words = set(saved_description.split())
        overlap = len(words & saved_words) / max(1, len(words | saved_words))
        same_kind = kind == saved_kind
        if ratio >= 0.86 or (same_kind and (ratio >= 0.72 or overlap >= 0.70)):
            return True
    return False

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
        error_text = str(exc).casefold()
        provider_status = getattr(exc, "status_code", None)
        if "timeout" in error_text or "timed out" in error_text:
            raise HTTPException(
                status_code=504,
                detail="O Gemini demorou demais para responder. Nenhuma sugestão nova foi salva nesta tentativa; tente novamente mais tarde.",
            ) from exc
        if provider_status in (429, 503, 504):
            raise HTTPException(
                status_code=503,
                detail="O Gemini está temporariamente indisponível ou limitou as chamadas. Nenhuma sugestão nova foi salva nesta tentativa; tente novamente mais tarde.",
            ) from exc
        raise HTTPException(status_code=502, detail="O serviço Gemini não conseguiu concluir a análise. Verifique a chave, o modelo e os limites da API.") from exc

    tables = {table.name for table in snapshot.tables}
    saved = [
        (_normalized_text(item.table_name), _normalized_text(item.kind), _normalized_text(item.description))
        for item in db.scalars(select(Suggestion)).all()
    ]
    created = []
    duplicates_skipped = 0
    for proposal in analysis.suggestions:
        # Model output is untrusted: only attach proposals to tables in this snapshot.
        if proposal.table not in tables:
            continue
        if _is_duplicate(proposal, saved):
            duplicates_skipped += 1
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
        saved.append((
            _normalized_text(item.table_name),
            _normalized_text(item.kind),
            _normalized_text(item.description),
        ))
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
        "duplicates_skipped": duplicates_skipped,
        "suggestions": [
            {"id": item.id, "table": item.table_name, "kind": item.kind,
             "description": item.description, "confidence": item.confidence,
             "status": item.status, "rationale": item.rationale}
            for item in created
        ],
        "human_review_required": True,
        "database_changes_applied": False,
    }
