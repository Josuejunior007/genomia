"""Contratos Pydantic da API do GenomAI.

Os modelos aqui são a fonte de verdade para o OpenAPI e para o frontend. Campos
de sugestão carregam o histórico de edição e o estado de aplicação para que a
interface consiga exibir o fluxo completo de governança.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Catálogo / análise estrutural
# ---------------------------------------------------------------------------


class ColumnInfo(BaseModel):
    """Coluna de uma tabela, sem qualquer valor de registro."""

    name: str
    type: str
    nullable: bool
    default: str | None = None
    is_primary_key: bool = False


class ForeignKeyInfo(BaseModel):
    """Chave estrangeira declarada no banco analisado."""

    constrained_columns: list[str]
    referred_table: str
    referred_schema: str = "public"
    referred_columns: list[str]


class IndexInfo(BaseModel):
    """Índice declarado no banco analisado."""

    name: str
    column_names: list[str]
    unique: bool


class TableInfo(BaseModel):
    """Metadados completos de uma tabela."""

    name: str
    schema: str = "public"
    columns: list[ColumnInfo]
    primary_key: list[str]
    foreign_keys: list[ForeignKeyInfo]
    indexes: list[IndexInfo]


class SchemaSnapshot(BaseModel):
    """Fotografia estrutural do schema analisado."""

    database: str
    schema: str
    tables: list[TableInfo]


class TableRows(BaseModel):
    """Página de registros, usada apenas na interface de exploração."""

    table: str
    schema: str
    columns: list[ColumnInfo]
    rows: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class RelationshipInfo(BaseModel):
    """Relacionamento de chave estrangeira entre duas tabelas."""

    constraint_name: str = ""
    source_table: str
    source_schema: str
    source_columns: list[str]
    target_table: str
    target_schema: str
    target_columns: list[str]


class TableRelationships(BaseModel):
    """Relacionamentos de saída e de entrada de uma tabela."""

    table: str
    schema: str
    outbound: list[RelationshipInfo]
    inbound: list[RelationshipInfo]


class Recommendation(BaseModel):
    """Recomendação determinística ou candidata produzida por IA."""

    severity: str = Field(pattern="^(low|medium|high)$")
    table: str
    category: str
    message: str
    suggested_sql: str | None = None
    evidence: str | None = None


class AnalysisReport(BaseModel):
    """Relatório da análise estrutural determinística."""

    summary: str
    tables_analyzed: int
    recommendations: list[Recommendation]


# ---------------------------------------------------------------------------
# Sugestões / revisão humana
# ---------------------------------------------------------------------------


class SuggestionCreate(BaseModel):
    """Dados para registrar uma sugestão no banco interno."""

    table: str = Field(min_length=1, max_length=255)
    kind: str = Field(min_length=1, max_length=40)
    column_name: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=5000)
    suggested_sql: str | None = Field(default=None, max_length=5000)


class SuggestionUpdate(BaseModel):
    """Edição humana de uma sugestão.

    A edição sempre gera uma revisão imutável em ``suggestion_revisions``. Se
    ``reopen`` for verdadeiro (padrão), a sugestão volta para ``pending`` para
    nova decisão, inclusive quando havia sido parcialmente aprovada.
    """

    table: str | None = Field(default=None, min_length=1, max_length=255)
    kind: str | None = Field(default=None, min_length=1, max_length=40)
    column_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    rationale: str | None = Field(default=None, min_length=1, max_length=5000)
    suggested_sql: str | None = Field(default=None, max_length=5000)
    comment: str = Field(default="", max_length=1000)
    reopen: bool = True

    @model_validator(mode="after")
    def _require_change(self) -> "SuggestionUpdate":
        """Impede PATCH vazio, que só geraria ruído no histórico."""
        changed = any(
            getattr(self, field) is not None
            for field in (
                "table",
                "kind",
                "column_name",
                "description",
                "confidence",
                "rationale",
                "suggested_sql",
            )
        )
        if not changed:
            raise ValueError("Informe ao menos um campo para editar.")
        return self


class ReviewRequest(BaseModel):
    """Decisão humana sobre uma sugestão."""

    decision: str = Field(pattern="^(approved|rejected|partially_approved)$")
    comment: str = Field(default="", max_length=1000)


class ReviewResponse(BaseModel):
    """Resposta de uma revisão concluída."""

    id: int
    status: str
    comment: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    version: int = 1


class ReviewItem(BaseModel):
    """Sugestão exposta para a interface de revisão."""

    id: int
    table: str
    kind: str
    column_name: str | None = None
    description: str
    confidence: float
    status: str = "pending"
    rationale: str
    suggested_sql: str | None = None
    version: int = 1
    previous_status: str | None = None
    review_comment: str = ""
    reviewed_by: str | None = None
    edited_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    reviewed_at: datetime | None = None
    applied_at: datetime | None = None
    applied_by: str | None = None
    apply_error: str | None = None
    revision_count: int = 0

    @property
    def is_applied(self) -> bool:
        """Compatibilidade de leitura no frontend."""
        return self.applied_at is not None


class SuggestionRevisionItem(BaseModel):
    """Versão histórica de uma sugestão."""

    id: int
    suggestion_id: int
    version: int
    table: str
    kind: str
    column_name: str | None = None
    description: str
    confidence: float
    status: str
    rationale: str
    suggested_sql: str | None = None
    edited_by: str
    comment: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Aplicação controlada no banco analisado
# ---------------------------------------------------------------------------


class ApplyPreview(BaseModel):
    """Prévia do SQL que seria executado, com bloqueios explícitos."""

    suggestion_id: int
    action: str
    sql: str | None = None
    can_apply: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApplyResponse(BaseModel):
    """Resultado de uma tentativa de aplicação."""

    suggestion_id: int
    action: str
    success: bool
    sql: str | None = None
    error: str | None = None
    applied_at: datetime | None = None
    applied_by: str | None = None
    log_id: int | None = None


class ApplyLogItem(BaseModel):
    """Registro de auditoria de aplicação."""

    id: int
    suggestion_id: int | None
    persona: str
    action: str
    sql_text: str
    success: bool
    error: str | None = None
    duration_ms: int | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Personas / armazenamento / privacidade
# ---------------------------------------------------------------------------


class PersonaItem(BaseModel):
    """Persona disponível e suas capacidades."""

    id: str
    label: str
    description: str
    capabilities: list[str]


class StorageInfo(BaseModel):
    """Diagnóstico das três conexões e do isolamento."""

    analyzed: dict[str, Any]
    app_store: dict[str, Any]
    isolation: dict[str, Any]
    ai: dict[str, Any]


class PrivacyAuditItem(BaseModel):
    """Auditoria de um envio de metadados à IA, sem conteúdo do payload."""

    id: int
    provider: str
    model: str
    payload_sha256: str
    tables_count: int
    columns_count: int
    sensitive_columns_count: int
    redacted_identifiers_count: int
    removed_fields_count: int
    excluded_tables: list[str] = Field(default_factory=list)
    triggered_by: str
    status: str
    created_at: datetime


class AiPayloadPreview(BaseModel):
    """Prévia exata do payload que seria enviado à IA."""

    payload: dict[str, Any]
    report: dict[str, Any]
    sha256: str
    policy: dict[str, Any]
