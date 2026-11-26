"""Rotas de sistema: personas, isolamento de armazenamento e privacidade da IA.

Estas rotas tornam explícitos os invariantes do projeto:

* o banco analisado é somente leitura;
* o armazenamento interno é uma conexão/schema separado;
* a IA recebe apenas metadados seguros, com prévia auditável e hash.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.personas import READ, Persona, persona_catalog, require_capability
from app.db.app_session import app_engine, app_store_info, get_app_db, validate_store_isolation
from app.db.session import engine
from app.models.audit import AiMetadataAudit
from app.privacy.metadata import (
    SAFE_METADATA_POLICY,
    build_safe_schema_context,
    privacy_policy_payload,
)
from app.schemas.schema import (
    AiPayloadPreview,
    PersonaItem,
    PrivacyAuditItem,
    StorageInfo,
)
from app.services.schema_service import SchemaService

router = APIRouter()

ViewerDep = Depends(require_capability(READ))


@router.get("/personas", response_model=list[PersonaItem], summary="Listar personas")
def list_personas(_persona: Persona = ViewerDep):
    """Retorna a matriz de personas e capacidades usada pelo frontend."""
    return persona_catalog()


@router.get(
    "/system/storage",
    response_model=StorageInfo,
    summary="Diagnóstico de isolamento dos bancos",
)
def storage_info(_persona: Persona = ViewerDep):
    """Explica onde ficam análise, armazenamento interno e escrita opcional."""
    warnings: list[str] = []
    isolation_error: str | None = None
    try:
        warnings = validate_store_isolation(engine)
    except RuntimeError as exc:
        isolation_error = str(exc)

    analyzed = {
        "dialect": engine.dialect.name,
        "schema": settings.db_schema,
        "read_only": True,
        "excluded_tables": sorted(settings.analysis_exclusion_set),
    }
    store = app_store_info()
    same_connection = app_engine.url == engine.url
    separate_storage = app_engine is not engine and not same_connection
    isolation = {
        "separate_connection": separate_storage,
        "separate_storage": separate_storage,
        "separate_schema": (
            settings.app_store_schema is not None
            and settings.app_store_schema.casefold() != settings.db_schema.casefold()
        ),
        "ai_receives_only_safe_metadata": True,
        "same_connection_string": same_connection,
        "valid": isolation_error is None,
        "error": isolation_error,
        "warnings": warnings,
    }
    ai = {
        "enabled": settings.ai_enabled,
        "provider": "groq",
        "model": settings.groq_model,
        "payload_policy": SAFE_METADATA_POLICY,
        "write_access": False,
        "applies_changes": False,
    }
    return StorageInfo(
        analyzed=analyzed,
        app_store=store,
        isolation=isolation,
        ai=ai,
    )


@router.get(
    "/privacy/policy",
    summary="Consultar política de privacidade da IA",
)
def privacy_policy(_persona: Persona = ViewerDep):
    """Lista campos permitidos, proibidos, categorias sensíveis e exclusões."""
    return privacy_policy_payload()


@router.get(
    "/privacy/ai-payload",
    response_model=AiPayloadPreview,
    summary="Pré-visualizar exatamente o payload enviado à IA",
)
def preview_ai_payload(_persona: Persona = ViewerDep):
    """Gera o payload seguro sem chamar nenhum provedor de IA.

    Útil para auditoria: mostra o JSON, o relatório de redações e o SHA-256.
    Nenhum registro, default ou valor de coluna aparece aqui.
    """
    try:
        snapshot = SchemaService(engine, settings.db_schema).snapshot()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível ler os metadados para montar o payload de IA.",
        ) from exc
    safe = build_safe_schema_context(snapshot)
    return AiPayloadPreview(
        payload=safe.payload.model_dump(mode="json"),
        report=safe.report.model_dump(mode="json"),
        sha256=safe.sha256,
        policy=privacy_policy_payload(),
    )


@router.get(
    "/privacy/audits",
    response_model=list[PrivacyAuditItem],
    summary="Consultar auditorias de envio de metadados à IA",
)
def list_privacy_audits(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_app_db),
    _persona: Persona = ViewerDep,
):
    """Lista hashes e contagens de envios anteriores, sem conteúdo do payload."""
    audits = db.scalars(
        select(AiMetadataAudit)
        .order_by(AiMetadataAudit.created_at.desc(), AiMetadataAudit.id.desc())
        .limit(limit)
    ).all()
    items: list[PrivacyAuditItem] = []
    for audit in audits:
        try:
            excluded = json.loads(audit.excluded_tables or "[]")
        except json.JSONDecodeError:
            excluded = []
        items.append(
            PrivacyAuditItem(
                id=audit.id,
                provider=audit.provider,
                model=audit.model,
                payload_sha256=audit.payload_sha256,
                tables_count=audit.tables_count,
                columns_count=audit.columns_count,
                sensitive_columns_count=audit.sensitive_columns_count,
                redacted_identifiers_count=audit.redacted_identifiers_count,
                removed_fields_count=audit.removed_fields_count,
                excluded_tables=excluded,
                triggered_by=audit.triggered_by,
                status=audit.status,
                created_at=audit.created_at,
            )
        )
    return items
