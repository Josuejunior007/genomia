"""Read-only access to table rows and foreign-key relationships."""

from __future__ import annotations

import datetime as dt
import math
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.schemas.schema import (
    ColumnInfo,
    RelationshipInfo,
    TableRelationships,
    TableRows,
)

DEFAULT_ROW_LIMIT = 25
MAX_ROW_LIMIT = 200


class TableNotFoundError(Exception):
    """Raised when the requested table is not part of the configured schema."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        super().__init__(f"Tabela não encontrada no schema configurado: {table_name}")


def jsonable(value: Any) -> Any:
    """Convert a database value into something FastAPI can serialize as JSON."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    return str(value)


class TableDataService:
    """Read rows and relationships without ever issuing a write statement."""

    def __init__(
        self,
        engine: Engine,
        schema_name: str = "public",
        default_limit: int = DEFAULT_ROW_LIMIT,
        max_limit: int = MAX_ROW_LIMIT,
    ):
        self.engine = engine
        self.schema_name = schema_name
        self.default_limit = default_limit
        self.max_limit = max_limit

    def _quote(self, name: str) -> str:
        return self.engine.dialect.identifier_preparer.quote(name)

    def _qualified(self, table_name: str) -> str:
        schema = self.engine.dialect.identifier_preparer.quote_schema(self.schema_name)
        return f"{schema}.{self._quote(table_name)}"

    def _describe(self, table_name: str, inspector) -> tuple[list[ColumnInfo], list[str]]:
        table_names = inspector.get_table_names(schema=self.schema_name)
        if table_name not in table_names:
            raise TableNotFoundError(table_name)

        primary_key = (
            inspector.get_pk_constraint(table_name, schema=self.schema_name).get(
                "constrained_columns"
            )
            or []
        )
        primary_key_set = set(primary_key)
        columns = [
            ColumnInfo(
                name=column["name"],
                type=str(column["type"]),
                nullable=column.get("nullable", True),
                default=None if column.get("default") is None else str(column["default"]),
                is_primary_key=column["name"] in primary_key_set,
            )
            for column in inspector.get_columns(table_name, schema=self.schema_name)
        ]
        return columns, list(primary_key)

    def rows(
        self,
        table_name: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> TableRows:
        """Return one page of rows ordered by the primary key when available."""
        page_size = self.default_limit if limit is None else limit
        if not 1 <= page_size <= self.max_limit:
            raise ValueError(f"limit deve estar entre 1 e {self.max_limit}")
        if offset < 0:
            raise ValueError("offset não pode ser negativo")

        inspector = inspect(self.engine)
        columns, primary_key = self._describe(table_name, inspector)
        qualified = self._qualified(table_name)
        order_by = ""
        if primary_key:
            order_by = " ORDER BY " + ", ".join(self._quote(column) for column in primary_key)

        with self.engine.connect() as connection:
            total = connection.execute(text(f"SELECT count(*) FROM {qualified}")).scalar_one()
            result = connection.execute(
                text(f"SELECT * FROM {qualified}{order_by} LIMIT :limit OFFSET :offset"),
                {"limit": page_size, "offset": offset},
            )
            rows = [
                {key: jsonable(value) for key, value in record._mapping.items()}
                for record in result
            ]

        return TableRows(
            table=table_name,
            schema=self.schema_name,
            columns=columns,
            rows=rows,
            total=int(total),
            limit=page_size,
            offset=offset,
        )

    def relationships(self, table_name: str) -> TableRelationships:
        """Return both foreign keys owned by the table and keys pointing at it."""
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names(schema=self.schema_name)
        if table_name not in table_names:
            raise TableNotFoundError(table_name)

        outbound: list[RelationshipInfo] = []
        inbound: list[RelationshipInfo] = []
        for source_table in table_names:
            for foreign_key in inspector.get_foreign_keys(
                source_table, schema=self.schema_name
            ):
                target_schema = foreign_key.get("referred_schema") or self.schema_name
                relationship = RelationshipInfo(
                    constraint_name=foreign_key.get("name") or "",
                    source_table=source_table,
                    source_schema=self.schema_name,
                    source_columns=list(foreign_key.get("constrained_columns") or []),
                    target_table=foreign_key.get("referred_table") or "",
                    target_schema=target_schema,
                    target_columns=list(foreign_key.get("referred_columns") or []),
                )
                if source_table == table_name:
                    outbound.append(relationship)
                if (
                    relationship.target_table == table_name
                    and target_schema == self.schema_name
                ):
                    inbound.append(relationship)

        return TableRelationships(
            table=table_name,
            schema=self.schema_name,
            outbound=outbound,
            inbound=inbound,
        )
