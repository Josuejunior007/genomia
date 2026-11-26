"""Rotas de sugestões: criação, edição versionada, revisão e aplicação.

O fluxo é sempre humano-no-controle:

1. Uma sugestão é criada (por regra, IA ou pessoa) como ``pending``.
2. Uma persona ``analista`` pode editar, aprovar, rejeitar ou aprovar
   parcialmente. Editar reabre a sugestão e gera uma revisão imutável.
3. Uma persona ``desenvolvedor``/``administrador`` pode pré-visualizar e
   aplicar mudanças dos tipos suportados, com SQL gerado pelo servidor.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.personas import (
    APPLY,
    AUDIT,
    READ,
    REVIEW,
    SUGGEST,
    Persona,
    require_capability,
)
from app.db.app_session import get_app_db
from app.db.session import engine
from app.db.write_session import get_write_engine
from app.models.audit import ApplyLog, SuggestionRevision
from app.models.suggestion import Suggestion
from app.schemas.schema import (
    ApplyLogItem,
    ApplyPreview,
    ApplyResponse,
    ReviewItem,
    ReviewRequest,
    ReviewResponse,
    SuggestionCreate,
    SuggestionRevisionItem,
    SuggestionUpdate,
)
from app.services.change_apply_service import (
    ApplyBlockedError,
    ApplyContext,
    ChangeApplyService,
)
from app.services.schema_service import SchemaService

router = APIRouter()

ALLOWED_KINDS = {
    "documentation",
    "relationship",
    "index",
    "integrity",
    "naming",
    "review",
}

ViewerDep = Depends(require_capability(READ))
SuggestDep = Depends(require_capability(SUGGEST))
ReviewDep = Depends(require_capability(REVIEW))
ApplyDep = Depends(require_capability(APPLY))
AuditDep = Depends(require_capability(AUDIT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _revision_count(db: Session, suggestion_id: int) -> int:
    """Conta revisões de uma sugestão específica."""
    return (
        db.scalar(
            select(func.count())
            .select_from(SuggestionRevision)
            .where(SuggestionRevision.suggestion_id == suggestion_id)
        )
        or 0
    )


def _response(item: Suggestion, revision_count: int = 0) -> ReviewItem:
    """Converte o modelo ORM no contrato público da API."""
    return ReviewItem(
        id=item.id,
        table=item.table_name,
        kind=item.kind,
        column_name=item.column_name,
        description=item.description,
        confidence=item.confidence,
        status=item.status,
        rationale=item.rationale,
        suggested_sql=item.suggested_sql,
        version=item.version or 1,
        previous_status=item.previous_status,
        review_comment=item.review_comment or "",
        reviewed_by=item.reviewed_by,
        edited_by=item.edited_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        reviewed_at=item.reviewed_at,
        applied_at=item.applied_at,
        applied_by=item.applied_by,
        apply_error=item.apply_error,
        revision_count=revision_count,
    )


def _load(db: Session, suggestion_id: int) -> Suggestion:
    """Carrega uma sugestão ou devolve 404."""
    item = db.get(Suggestion, suggestion_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada.")
    return item


def _resolve_target(table_name: str, column_name: str | None) -> tuple[str, str | None]:
    """Valida tabela/coluna contra o snapshot e devolve nomes canônicos.

    Tabelas do armazenamento interno são rejeitadas explicitamente para que a
    IA (ou uma pessoa) não crie sugestões sobre o próprio banco de sugestões.
    """
    try:
        service = SchemaService(engine, settings.db_schema)
        table = service.table(table_name)
        if table is None:
            table = next(
                (
                    candidate
                    for candidate in service.snapshot().tables
                    if candidate.name.casefold() == table_name.casefold()
                ),
                None,
            )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível validar a tabela no banco analisado.",
        ) from exc

    if table is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Tabela {table_name!r} não encontrada no schema analisado ou "
                "reservada ao armazenamento interno do GenomAI."
            ),
        )

    resolved_column = None
    if column_name:
        match = next(
            (
                column
                for column in table.columns
                if column.name.casefold() == column_name.casefold()
            ),
            None,
        )
        if match is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Coluna {column_name!r} não encontrada na tabela "
                    f"{table.name!r}."
                ),
            )
        resolved_column = match.name
    return table.name, resolved_column


def _record_revision(
    db: Session,
    item: Suggestion,
    *,
    edited_by: str,
    comment: str,
) -> None:
    """Grava uma fotografia imutável da versão atual da sugestão."""
    db.add(
        SuggestionRevision(
            suggestion_id=item.id,
            version=item.version,
            table_name=item.table_name,
            kind=item.kind,
            column_name=item.column_name,
            description=item.description,
            confidence=item.confidence,
            status=item.status,
            rationale=item.rationale,
            suggested_sql=item.suggested_sql,
            edited_by=edited_by,
            comment=comment,
        )
    )


# ---------------------------------------------------------------------------
# CRUD / revisão
# ---------------------------------------------------------------------------


@router.get(
    "/suggestions",
    response_model=list[ReviewItem],
    summary="Listar sugestões para revisão",
)
def list_suggestions(
    status: str = Query(
        default="pending",
        pattern="^(pending|approved|rejected|partially_approved|all)$",
    ),
    table: str | None = Query(default=None, max_length=255),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_app_db),
    _persona: Persona = ViewerDep,
):
    """Lista sugestões com filtros de status, tabela e busca textual."""
    statement = select(Suggestion).order_by(
        Suggestion.created_at.desc(), Suggestion.id.desc()
    )
    if status != "all":
        statement = statement.where(Suggestion.status == status)
    if table:
        statement = statement.where(Suggestion.table_name == table)
    if q and q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                Suggestion.table_name.ilike(term),
                Suggestion.description.ilike(term),
                Suggestion.rationale.ilike(term),
            )
        )
    statement = statement.limit(limit).offset(offset)
    items = db.scalars(statement).all()

    counts: dict[int, int] = {}
    if items:
        rows = db.execute(
            select(
                SuggestionRevision.suggestion_id,
                func.count(),
            )
            .where(
                SuggestionRevision.suggestion_id.in_(
                    [item.id for item in items]
                )
            )
            .group_by(SuggestionRevision.suggestion_id)
        ).all()
        counts = {int(row[0]): int(row[1]) for row in rows}
    return [_response(item, counts.get(item.id, 0)) for item in items]


@router.post(
    "/suggestions",
    response_model=ReviewItem,
    status_code=201,
    summary="Registrar sugestão para revisão",
)
def create_suggestion(
    body: SuggestionCreate,
    db: Session = Depends(get_app_db),
    persona: Persona = SuggestDep,
):
    """Cria uma sugestão validando tabela, coluna e tipo contra o schema."""
    kind = body.kind.strip().casefold()
    if kind not in ALLOWED_KINDS:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo de sugestão inválido. Use um de: {', '.join(sorted(ALLOWED_KINDS))}.",
        )
    table_name, column_name = _resolve_target(body.table, body.column_name)
    item = Suggestion(
        table_name=table_name,
        kind=kind,
        column_name=column_name,
        description=body.description,
        confidence=body.confidence,
        rationale=body.rationale,
        suggested_sql=body.suggested_sql,
        edited_by=persona.value,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    _record_revision(db, item, edited_by=persona.value, comment="Criação da sugestão")
    db.commit()
    return _response(item, _revision_count(db, item.id))


@router.patch(
    "/suggestions/{suggestion_id}",
    response_model=ReviewItem,
    summary="Editar sugestão e gerar nova versão",
)
def update_suggestion(
    suggestion_id: int,
    body: SuggestionUpdate,
    db: Session = Depends(get_app_db),
    persona: Persona = SuggestDep,
):
    """Edita uma sugestão; por padrão ela volta para ``pending``."""
    item = _load(db, suggestion_id)
    if item.applied_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Sugestão já aplicada não pode ser editada.",
        )
    if not body.reopen and item.status in ("approved", "partially_approved"):
        raise HTTPException(
            status_code=409,
            detail=(
                "Alterar o conteúdo de uma sugestão aprovada ou parcialmente "
                "aprovada exige reopen=true, para que haja nova decisão humana."
            ),
        )

    updates = body.model_dump(exclude_unset=True, exclude={"comment", "reopen"})
    # ``column_name=None`` é uma instrução válida (remover a coluna alvo); os
    # demais campos nulos são ignorados para não apagar conteúdo por engano.
    updates = {
        field: value
        for field, value in updates.items()
        if value is not None or field == "column_name"
    }
    if "kind" in updates and updates["kind"] is not None:
        kind = str(updates["kind"]).strip().casefold()
        if kind not in ALLOWED_KINDS:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Tipo de sugestão inválido. Use um de: "
                    f"{', '.join(sorted(ALLOWED_KINDS))}."
                ),
            )
        updates["kind"] = kind

    new_table = updates.get("table", item.table_name)
    new_column = updates.get("column_name", item.column_name)
    resolved_table, resolved_column = _resolve_target(str(new_table), new_column)
    if "table" in updates:
        updates["table"] = resolved_table
    if "column_name" in updates or (new_column and resolved_column != new_column):
        updates["column_name"] = resolved_column

    item.previous_status = item.status
    for field, value in updates.items():
        setattr(item, field, value)
    item.version = (item.version or 1) + 1
    item.updated_at = datetime.now(timezone.utc)
    item.edited_by = persona.value
    if body.reopen:
        item.status = "pending"
        item.reviewed_at = None
    db.flush()
    _record_revision(db, item, edited_by=persona.value, comment=body.comment)
    db.commit()
    db.refresh(item)
    return _response(item, _revision_count(db, item.id))


@router.post(
    "/suggestions/{suggestion_id}/review",
    response_model=ReviewResponse,
    summary="Aprovar, rejeitar ou aprovar parcialmente uma sugestão",
)
def review_suggestion(
    suggestion_id: int,
    body: ReviewRequest,
    db: Session = Depends(get_app_db),
    persona: Persona = ReviewDep,
):
    """Registra a decisão humana sem aplicar qualquer mudança no banco."""
    item = _load(db, suggestion_id)
    if item.applied_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Sugestão já aplicada não pode ser revisada novamente.",
        )
    if item.status == body.decision:
        raise HTTPException(
            status_code=409,
            detail=f"A sugestão já está com status {body.decision!r}.",
        )

    item.previous_status = item.status
    item.status = body.decision
    item.review_comment = body.comment
    item.reviewed_by = persona.value
    item.reviewed_at = datetime.now(timezone.utc)
    item.updated_at = item.reviewed_at
    db.commit()
    db.refresh(item)
    return ReviewResponse(
        id=item.id,
        status=item.status,
        comment=item.review_comment,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
        version=item.version,
    )


@router.get(
    "/suggestions/{suggestion_id}/revisions",
    response_model=list[SuggestionRevisionItem],
    summary="Listar versões de uma sugestão",
)
def list_revisions(
    suggestion_id: int,
    db: Session = Depends(get_app_db),
    _persona: Persona = ViewerDep,
):
    """Retorna o histórico imutável de edições da sugestão."""
    _load(db, suggestion_id)
    revisions = db.scalars(
        select(SuggestionRevision)
        .where(SuggestionRevision.suggestion_id == suggestion_id)
        .order_by(SuggestionRevision.version.asc(), SuggestionRevision.id.asc())
    ).all()
    return [
        SuggestionRevisionItem(
            id=revision.id,
            suggestion_id=revision.suggestion_id,
            version=revision.version,
            table=revision.table_name,
            kind=revision.kind,
            column_name=revision.column_name,
            description=revision.description,
            confidence=revision.confidence,
            status=revision.status,
            rationale=revision.rationale,
            suggested_sql=revision.suggested_sql,
            edited_by=revision.edited_by,
            comment=revision.comment,
            created_at=revision.created_at,
        )
        for revision in revisions
    ]


# ---------------------------------------------------------------------------
# Aplicação controlada
# ---------------------------------------------------------------------------


def _apply_service(db: Session, persona: Persona) -> ChangeApplyService:
    """Monta o serviço de aplicação com a conexão de escrita opcional."""
    return ChangeApplyService(
        ApplyContext(
            app_db=db,
            analyzed_engine=engine,
            write_engine=get_write_engine(),
            persona=persona.value,
            schema=settings.db_schema,
        )
    )


@router.get(
    "/suggestions/{suggestion_id}/apply-preview",
    response_model=ApplyPreview,
    summary="Pré-visualizar SQL de aplicação",
)
def preview_apply(
    suggestion_id: int,
    db: Session = Depends(get_app_db),
    persona: Persona = ApplyDep,
):
    """Mostra o SQL server-side e os bloqueios antes de aplicar."""
    item = _load(db, suggestion_id)
    return _apply_service(db, persona).preview(item)


@router.post(
    "/suggestions/{suggestion_id}/apply",
    response_model=ApplyResponse,
    summary="Aplicar mudança aprovada no banco analisado",
)
def apply_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_app_db),
    persona: Persona = ApplyDep,
):
    """Aplica uma mudança aprovada, com auditoria e validação de schema."""
    item = _load(db, suggestion_id)
    service = _apply_service(db, persona)
    try:
        return service.apply(item)
    except ApplyBlockedError as exc:
        raise HTTPException(
            status_code=409,
            detail=exc.preview.model_dump(mode="json"),
        ) from exc


@router.get(
    "/apply-logs",
    response_model=list[ApplyLogItem],
    summary="Consultar auditoria de aplicações",
)
def list_apply_logs(
    suggestion_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_app_db),
    _persona: Persona = AuditDep,
):
    """Lista tentativas de aplicação, com sucesso/falha e SQL executado."""
    statement = select(ApplyLog).order_by(ApplyLog.created_at.desc(), ApplyLog.id.desc())
    if suggestion_id is not None:
        statement = statement.where(ApplyLog.suggestion_id == suggestion_id)
    logs = db.scalars(statement.limit(limit)).all()
    return [
        ApplyLogItem(
            id=log.id,
            suggestion_id=log.suggestion_id,
            persona=log.persona,
            action=log.action,
            sql_text=log.sql_text,
            success=log.success,
            error=log.error,
            duration_ms=log.duration_ms,
            created_at=log.created_at,
        )
        for log in logs
    ]
