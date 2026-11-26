"""Aplicação controlada de mudanças aprovadas no banco analisado.

Regras de segurança:

* Só executa ``CREATE INDEX`` e ``COMMENT ON`` gerados pelo **servidor**.
* Nunca executa o SQL candidato produzido pela IA; ele é apenas informativo.
* Exige sugestão ``approved``, persona ``desenvolvedor``/``administrador`` e
  ``DB_WRITE_ENABLED=true`` com ``WRITE_DATABASE_URL`` configurada.
* Valida tabela e coluna contra o snapshot atual antes de executar.
* Registra cada tentativa em ``apply_logs`` (sucesso ou falha).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import ApplyLog
from app.models.suggestion import Suggestion
from app.schemas.schema import ApplyPreview, ApplyResponse
from app.services.schema_service import SchemaService

SUPPORTED_KINDS = {"index", "documentation"}
MAX_COMMENT_LENGTH = 1000


class ApplyBlockedError(Exception):
    """Mudança não pode ser aplicada; carrega a prévia com os bloqueios."""

    def __init__(self, preview: ApplyPreview):
        self.preview = preview
        super().__init__("; ".join(preview.blockers) or "Aplicação bloqueada.")


@dataclass
class ApplyContext:
    """Dependências necessárias para pré-visualizar/aplicar uma mudança."""

    app_db: Session
    analyzed_engine: Engine
    write_engine: Engine | None
    persona: str
    schema: str = "public"
    warnings: list[str] = field(default_factory=list)


def _quote_ident(engine: Engine, value: str) -> str:
    """Cita um identificador de forma conservadora em qualquer dialeto."""
    return engine.dialect.identifier_preparer.quote_identifier(value)


def _quote_qualified(engine: Engine, schema: str, table: str) -> str:
    """Cita ``schema.tabela`` conforme o dialeto."""
    preparer = engine.dialect.identifier_preparer
    return f"{preparer.quote_identifier(schema)}.{preparer.quote_identifier(table)}"


def _quote_literal(value: str) -> str:
    """Escapa um literal de texto para DDL de comentário (PostgreSQL)."""
    cleaned = value.replace("\x00", " ").strip()
    return "'" + cleaned.replace("'", "''") + "'"


def _index_name(schema: str, table: str, column: str) -> str:
    """Gera um nome determinístico, curto e seguro para o índice."""
    digest = hashlib.sha1(f"{schema}.{table}.{column}".encode("utf-8")).hexdigest()[:8]
    base = f"idx_{table}_{column}_{digest}".lower()
    safe = "".join(char if char.isalnum() or char == "_" else "_" for char in base)
    return safe[:63]


class ChangeApplyService:
    """Orquestra prévia, execução e auditoria de mudanças no banco alvo."""

    def __init__(self, context: ApplyContext):
        self.context = context

    # -- prévia ----------------------------------------------------------
    def preview(self, suggestion: Suggestion) -> ApplyPreview:
        """Valida a sugestão e monta o SQL que seria executado."""
        blockers: list[str] = []
        warnings = list(self.context.warnings)
        action = (suggestion.kind or "").strip().casefold()

        if suggestion.applied_at is not None:
            blockers.append("Esta sugestão já foi aplicada.")
        if suggestion.status != "approved":
            blockers.append(
                "A sugestão precisa estar aprovada antes de ser aplicada "
                f"(status atual: {suggestion.status})."
            )
        if action not in SUPPORTED_KINDS:
            blockers.append(
                "Aplicação automática disponível apenas para 'index' e "
                "'documentation'. Para integridade/relacionamento, use o SQL "
                "candidato como referência e aplique manualmente."
            )
        if not settings.db_write_enabled:
            blockers.append("Escrita desativada: defina DB_WRITE_ENABLED=true.")
        if self.context.write_engine is None:
            blockers.append("Conexão de escrita ausente: defina WRITE_DATABASE_URL.")
        if self.context.write_engine is not None and (
            settings.write_database_url
            and str(self.context.write_engine.url)
            == str(self.context.analyzed_engine.url)
        ):
            blockers.append(
                "WRITE_DATABASE_URL é igual à conexão analisada (somente leitura). "
                "Use uma role de escrita dedicada."
            )

        sql: str | None = None
        if not blockers or action in SUPPORTED_KINDS:
            try:
                sql, more_blockers, more_warnings = self._build_sql(suggestion, action)
                blockers.extend(more_blockers)
                warnings.extend(more_warnings)
            except Exception as exc:  # validação defensiva
                blockers.append(f"Não foi possível montar o SQL: {exc}")

        return ApplyPreview(
            suggestion_id=suggestion.id,
            action=action,
            sql=sql,
            can_apply=not blockers,
            blockers=blockers,
            warnings=warnings,
        )

    def _find_table(self, table_name: str):
        snapshot = SchemaService(
            self.context.analyzed_engine, self.context.schema
        ).snapshot()
        target = table_name.casefold()
        return snapshot, next(
            (table for table in snapshot.tables if table.name.casefold() == target),
            None,
        )

    def _build_sql(
        self, suggestion: Suggestion, action: str
    ) -> tuple[str | None, list[str], list[str]]:
        """Gera SQL server-side a partir de campos validados."""
        blockers: list[str] = []
        warnings = [
            "SQL gerado pelo servidor a partir de metadados validados; "
            "o SQL candidato da IA não é executado."
        ]
        engine = self.context.write_engine or self.context.analyzed_engine
        snapshot, table = self._find_table(suggestion.table_name)
        if table is None:
            return None, ["Tabela não encontrada no schema analisado."], warnings

        qualified = _quote_qualified(engine, self.context.schema, table.name)
        column = (suggestion.column_name or "").strip()

        if action == "index":
            if not column:
                return (
                    None,
                    [
                        "Informe a coluna alvo (column_name) para gerar o índice. "
                        "Edite a sugestão antes de aplicar."
                    ],
                    warnings,
                )
            column_names = {item.name.casefold() for item in table.columns}
            if column.casefold() not in column_names:
                return (
                    None,
                    [f"Coluna {column!r} não existe na tabela {table.name!r}."],
                    warnings,
                )
            indexed_leading = {
                index.column_names[0].casefold()
                for index in table.indexes
                if index.column_names
            }
            indexed_leading.update(item.casefold() for item in table.primary_key)
            if column.casefold() in indexed_leading:
                return (
                    None,
                    [
                        f"A coluna {column!r} já é a primeira coluna de um índice "
                        "ou da chave primária; criar outro índice seria redundante."
                    ],
                    warnings,
                )
            index_name = _index_name(self.context.schema, table.name, column)
            index_ref = _quote_ident(engine, index_name)
            if engine.dialect.name == "postgresql":
                index_ref = (
                    f"{engine.dialect.identifier_preparer.quote_identifier(self.context.schema)}."
                    f"{index_ref}"
                )
                target = qualified
            elif engine.dialect.name == "sqlite":
                # SQLite qualifica o *nome do índice* com o schema; a tabela no
                # ON não aceita schema.tabela na sintaxe de CREATE INDEX.
                index_ref = (
                    f"{engine.dialect.identifier_preparer.quote_identifier(self.context.schema)}."
                    f"{index_ref}"
                )
                target = _quote_ident(engine, table.name)
            else:
                target = qualified
            sql = (
                f"CREATE INDEX {index_ref} ON {target} "
                f"({_quote_ident(engine, column)});"
            )
            return sql, blockers, warnings

        # documentation -> COMMENT ON
        if engine.dialect.name != "postgresql":
            return (
                None,
                [
                    "Comentários de documentação são suportados automaticamente "
                    "apenas em PostgreSQL. Gere e aplique manualmente neste SGBD."
                ],
                warnings,
            )
        comment = (suggestion.description or "").strip()
        if not comment:
            return None, ["Descrição vazia; não há comentário para aplicar."], warnings
        if len(comment) > MAX_COMMENT_LENGTH:
            comment = comment[:MAX_COMMENT_LENGTH]
            warnings.append(
                f"Comentário truncado em {MAX_COMMENT_LENGTH} caracteres."
            )
        if column:
            column_names = {item.name.casefold() for item in table.columns}
            if column.casefold() not in column_names:
                return (
                    None,
                    [f"Coluna {column!r} não existe na tabela {table.name!r}."],
                    warnings,
                )
            sql = (
                f"COMMENT ON COLUMN {qualified}.{_quote_ident(engine, column)} "
                f"IS {_quote_literal(comment)};"
            )
        else:
            sql = f"COMMENT ON TABLE {qualified} IS {_quote_literal(comment)};"
        return sql, blockers, warnings

    # -- execução --------------------------------------------------------
    def apply(self, suggestion: Suggestion) -> ApplyResponse:
        """Executa a mudança se a prévia permitir e audita o resultado."""
        preview = self.preview(suggestion)
        if not preview.can_apply or not preview.sql:
            raise ApplyBlockedError(preview)

        engine = self.context.write_engine
        assert engine is not None  # garantido pela prévia
        started = time.perf_counter()
        error: str | None = None
        success = False
        try:
            with engine.begin() as connection:
                connection.execute(text(preview.sql))
            success = True
        except Exception as exc:  # o erro é auditado e devolvido ao cliente
            error = str(exc)[:2000]
        duration_ms = int((time.perf_counter() - started) * 1000)

        now = datetime.now(timezone.utc)
        if success:
            suggestion.applied_at = now
            suggestion.applied_by = self.context.persona
            suggestion.apply_error = None
        else:
            suggestion.apply_error = error

        log = ApplyLog(
            suggestion_id=suggestion.id,
            persona=self.context.persona,
            action=preview.action,
            sql_text=preview.sql,
            success=success,
            error=error,
            duration_ms=duration_ms,
        )
        self.context.app_db.add(log)
        self.context.app_db.commit()
        self.context.app_db.refresh(log)
        self.context.app_db.refresh(suggestion)

        return ApplyResponse(
            suggestion_id=suggestion.id,
            action=preview.action,
            success=success,
            sql=preview.sql,
            error=error,
            applied_at=suggestion.applied_at,
            applied_by=suggestion.applied_by,
            log_id=log.id,
        )
