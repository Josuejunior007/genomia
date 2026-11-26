"""Modelos de auditoria e histórico do armazenamento interno."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, app_table_args


class SuggestionRevision(Base):
    """Versão imutável de uma sugestão após cada edição humana.

    O histórico permite responder "quem mudou o quê, quando e por quê" sem
    depender de logs da aplicação. Nenhum conteúdo desta tabela é enviado à IA.
    """

    __tablename__ = "suggestion_revisions"
    __table_args__ = app_table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    column_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_sql: Mapped[str | None] = mapped_column(Text, nullable=True)

    edited_by: Mapped[str] = mapped_column(String(80), nullable=False)
    comment: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ApplyLog(Base):
    """Trilha de auditoria de tentativas de aplicação de mudanças.

    Guarda o SQL gerado pelo servidor e o resultado. Não guarda dados de linhas
    do banco analisado.
    """

    __tablename__ = "apply_logs"
    __table_args__ = app_table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    persona: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AiMetadataAudit(Base):
    """Prova de que apenas metadados seguros foram enviados à IA.

    O conteúdo do payload **não** é armazenado: guardamos apenas um hash
    SHA-256, contagens e a política aplicada. Isso permite auditar sem criar
    uma segunda cópia de metadados.
    """

    __tablename__ = "ai_metadata_audits"
    __table_args__ = app_table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="groq")
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    tables_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    columns_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sensitive_columns_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    redacted_identifiers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    removed_fields_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Lista JSON com os nomes das tabelas excluídas por isolamento.
    excluded_tables: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    triggered_by: Mapped[str] = mapped_column(String(80), nullable=False, default="sistema")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
