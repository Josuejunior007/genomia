"""Rotas de análise estrutural e análise com IA.

A análise determinística lê apenas metadados. A análise com IA constrói o
payload por meio da camada de privacidade, registra um hash de auditoria e
persiste as propostas para revisão humana. A IA nunca recebe registros e nunca
executa mudanças.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.personas import SUGGEST, Persona, require_capability
from app.db.app_session import get_app_db
from app.db.session import engine
from app.models.audit import AiMetadataAudit
from app.models.suggestion import Suggestion
from app.privacy.metadata import build_safe_schema_context
from app.schemas.schema import AnalysisReport
from app.services.advisor_service import AdvisorService
from app.services.groq_advisor_service import GroqAdvisorService, GroqSuggestion
from app.services.schema_service import SchemaService

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_KINDS = {
    "documentation",
    "relationship",
    "index",
    "integrity",
    "naming",
    "review",
}

SuggestDep = Depends(require_capability(SUGGEST))


def _normalized_text(value: str) -> str:
    """Normaliza texto para comparação de duplicidade."""
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _is_duplicate(
    proposal: GroqSuggestion,
    saved: list[tuple[str, str, str, str]],
) -> bool:
    """Compara com propostas persistidas para não reencher a fila de revisão."""
    table = _normalized_text(proposal.table)
    kind = _normalized_text(proposal.kind)
    column = _normalized_text(proposal.column_name or "")
    description = _normalized_text(proposal.description)
    words = set(description.split())
    for saved_table, saved_kind, saved_column, saved_description in saved:
        if table != saved_table:
            continue
        ratio = SequenceMatcher(None, description, saved_description).ratio()
        saved_words = set(saved_description.split())
        overlap = len(words & saved_words) / max(1, len(words | saved_words))
        same_kind = kind == saved_kind
        same_column = column == saved_column
        if same_column and (ratio >= 0.86 or (same_kind and (ratio >= 0.72 or overlap >= 0.70))):
            return True
        if not column and not saved_column and (
            ratio >= 0.86 or (same_kind and (ratio >= 0.72 or overlap >= 0.70))
        ):
            return True
    return False


@router.get("/analyze", response_model=AnalysisReport, summary="Analisar qualidade estrutural")
def analyze_schema() -> AnalysisReport:
    """Executa regras determinísticas sobre os metadados do schema."""
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
        return AdvisorService().analyze(snapshot)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Análise indisponível: não foi possível consultar os metadados do banco.",
        )


@router.post(
    "/ai-analyze",
    summary="Analisar esquema com Groq e salvar propostas para revisão",
)
def analyze_schema_with_ai(
    db: Session = Depends(get_app_db),
    persona: Persona = SuggestDep,
):
    """Envia somente metadados seguros à Groq e persiste as propostas.

    O payload é construído por ``build_safe_schema_context`` e validado antes da
    chamada. Um registro em ``ai_metadata_audits`` guarda apenas hash/contagens.
    """
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=503,
            detail="Análise com IA desativada. Configure AI_ENABLED=true.",
        )
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="Configure GROQ_API_KEY no ambiente da API.",
        )

    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Análise indisponível: não foi possível consultar os metadados do banco.",
        )

    safe = build_safe_schema_context(snapshot)
    audit = AiMetadataAudit(
        provider="groq",
        model=settings.groq_model,
        payload_sha256=safe.sha256,
        tables_count=safe.report.tables_included,
        columns_count=safe.report.columns_included,
        sensitive_columns_count=safe.report.sensitive_columns,
        redacted_identifiers_count=safe.report.redacted_identifiers,
        removed_fields_count=safe.report.removed_fields,
        excluded_tables=json.dumps(safe.report.excluded_table_names, ensure_ascii=False),
        triggered_by=persona.value,
        status="started",
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    try:
        deterministic = AdvisorService().analyze(snapshot)
        analysis = GroqAdvisorService(settings.groq_api_key, settings.groq_model).analyze(
            safe.payload, deterministic
        )
    except Exception as exc:
        logger.exception("Falha ao consultar o Groq")
        audit.status = "failed"
        db.commit()
        error_text = str(exc).casefold()
        provider_status = getattr(exc, "status_code", None)
        if "timeout" in error_text or "timed out" in error_text:
            raise HTTPException(
                status_code=504,
                detail=(
                    "O Groq demorou demais para responder. Nenhuma sugestão nova foi "
                    "salva nesta tentativa; tente novamente mais tarde."
                ),
            ) from exc
        if provider_status in (429, 503, 504):
            raise HTTPException(
                status_code=503,
                detail=(
                    "O Groq está temporariamente indisponível ou limitou as chamadas. "
                    "Nenhuma sugestão nova foi salva nesta tentativa; tente novamente "
                    "mais tarde."
                ),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=(
                "O serviço Groq não conseguiu concluir a análise. Verifique a chave, "
                "o modelo e os limites da API."
            ),
        ) from exc

    audit.status = "success"
    db.commit()

    tables = {table.name.casefold(): table for table in snapshot.tables}
    saved = [
        (
            _normalized_text(item.table_name),
            _normalized_text(item.kind),
            _normalized_text(item.column_name or ""),
            _normalized_text(item.description),
        )
        for item in db.scalars(select(Suggestion)).all()
    ]
    created: list[Suggestion] = []
    duplicates_skipped = 0
    rejected_invalid = 0
    for proposal in analysis.suggestions:
        table = tables.get(proposal.table.casefold())
        if table is None:
            # Saída do modelo é não confiável: só aceita tabela do snapshot.
            rejected_invalid += 1
            continue
        column_name = None
        if proposal.column_name:
            match = next(
                (
                    column
                    for column in table.columns
                    if column.name.casefold() == proposal.column_name.casefold()
                ),
                None,
            )
            column_name = match.name if match else None
        kind = proposal.kind.strip().casefold()
        if kind not in ALLOWED_KINDS:
            kind = "review"
        if _is_duplicate(proposal, saved):
            duplicates_skipped += 1
            continue
        candidate_sql = proposal.suggested_sql.strip()
        if candidate_sql and not candidate_sql.upper().startswith(
            ("CREATE INDEX ", "CREATE UNIQUE INDEX ", "COMMENT ON ")
        ):
            candidate_sql = ""
        rationale = (
            f"Evidência: {proposal.evidence}\n\n"
            f"Riscos e incertezas: {proposal.risks_and_uncertainty}"
        )
        item = Suggestion(
            table_name=table.name,
            kind=kind[:40],
            column_name=column_name,
            description=proposal.description[:5000],
            confidence=proposal.confidence,
            rationale=rationale[:5000],
            suggested_sql=candidate_sql[:5000] or None,
        )
        db.add(item)
        created.append(item)
        saved.append(
            (
                _normalized_text(item.table_name),
                _normalized_text(item.kind),
                _normalized_text(item.column_name or ""),
                _normalized_text(item.description),
            )
        )
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
            {
                "id": item.id,
                "table": item.table_name,
                "kind": item.kind,
                "column_name": item.column_name,
                "description": item.description,
                "confidence": item.confidence,
                "status": item.status,
                "rationale": item.rationale,
                "suggested_sql": item.suggested_sql,
            }
            for item in created
        ],
        "human_review_required": True,
        "database_changes_applied": False,
        "privacy": {
            "policy": "safe-metadata-v1",
            "payload_sha256": safe.sha256,
            "tables_sent": safe.report.tables_included,
            "columns_sent": safe.report.columns_included,
            "sensitive_columns_flagged": safe.report.sensitive_columns,
            "redacted_identifiers": safe.report.redacted_identifiers,
            "excluded_tables": safe.report.excluded_table_names,
            "records_sent": 0,
            "defaults_sent": 0,
        },
    }
