"""Leitura de metadados do banco analisado.

A inspeção é estritamente estrutural: tabelas, colunas, tipos, nulabilidade,
chaves e índices. Nenhum registro é lido. Tabelas do armazenamento interno do
GenomAI são excluídas para impedir que a IA analise o próprio banco de
sugestões (o problema que originou uma sugestão sobre a tabela
``public.suggestions`` no Supabase).
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.schemas.schema import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    SchemaSnapshot,
    TableInfo,
)


class SchemaService:
    """Reflect do schema configurado, com exclusões de segurança."""

    def __init__(
        self,
        engine: Engine,
        schema_name: str = "public",
        excluded_tables: Iterable[str] | None = None,
    ):
        self.engine = engine
        self.schema_name = schema_name
        self.excluded_tables = {
            name.strip().casefold()
            for name in (
                settings.analysis_exclusion_set
                if excluded_tables is None
                else excluded_tables
            )
            if name and name.strip()
        }

    def _is_excluded(self, table_name: str) -> bool:
        """Indica se a tabela pertence ao armazenamento interno/ignorado."""
        return table_name.casefold() in self.excluded_tables

    def table(self, table_name: str) -> TableInfo | None:
        """Reflect uma única tabela, respeitando a lista de exclusão."""
        if self._is_excluded(table_name):
            return None
        inspector = inspect(self.engine)
        if table_name not in inspector.get_table_names(schema=self.schema_name):
            return None
        return self._build_table(inspector, table_name)

    def _build_table(self, inspector, table_name: str) -> TableInfo:
        """Monta o ``TableInfo`` a partir do inspector do SQLAlchemy."""
        columns = [
            ColumnInfo(
                name=column["name"],
                type=str(column["type"]),
                nullable=column.get("nullable", True),
                default=(
                    None if column.get("default") is None else str(column["default"])
                ),
                is_primary_key=False,
            )
            for column in inspector.get_columns(table_name, schema=self.schema_name)
        ]
        primary_key = (
            inspector.get_pk_constraint(table_name, schema=self.schema_name).get(
                "constrained_columns"
            )
            or []
        )
        primary_key_set = set(primary_key)
        for column in columns:
            column.is_primary_key = column.name in primary_key_set
        foreign_keys = [
            ForeignKeyInfo(
                constrained_columns=fk.get("constrained_columns") or [],
                referred_table=fk.get("referred_table") or "",
                referred_schema=fk.get("referred_schema") or self.schema_name,
                referred_columns=fk.get("referred_columns") or [],
            )
            for fk in inspector.get_foreign_keys(table_name, schema=self.schema_name)
            if not self._is_excluded(fk.get("referred_table") or "")
        ]
        indexes = [
            IndexInfo(
                name=index.get("name") or "",
                column_names=index.get("column_names") or [],
                unique=bool(index.get("unique")),
            )
            for index in inspector.get_indexes(table_name, schema=self.schema_name)
        ]
        return TableInfo(
            name=table_name,
            schema=self.schema_name,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
            indexes=indexes,
        )

    def snapshot(self) -> SchemaSnapshot:
        """Retorna todos os metadados do schema, exceto tabelas excluídas."""
        inspector = inspect(self.engine)
        tables = [
            self._build_table(inspector, table_name)
            for table_name in inspector.get_table_names(schema=self.schema_name)
            if not self._is_excluded(table_name)
        ]
        return SchemaSnapshot(
            database=self.engine.url.database or "postgres",
            schema=self.schema_name,
            tables=tables,
        )
