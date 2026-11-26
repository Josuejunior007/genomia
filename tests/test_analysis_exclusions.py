"""Testes de exclusão das tabelas internas do catálogo e da análise."""

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, create_engine

from app.services.schema_service import SchemaService
from app.services.table_data_service import TableDataService, TableNotFoundError


@pytest.fixture()
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    Table(
        "suggestions",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("description", String(100)),
    )
    Table(
        "clientes",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("nome", String(100)),
    )
    metadata.create_all(engine)
    return engine


def test_snapshot_excludes_internal_tables(engine):
    snapshot = SchemaService(engine, "main").snapshot()
    assert [table.name for table in snapshot.tables] == ["clientes"]


def test_single_table_and_rows_reject_internal_table(engine):
    service = SchemaService(engine, "main")
    assert service.table("suggestions") is None

    with pytest.raises(TableNotFoundError):
        TableDataService(engine, "main").rows("suggestions")


def test_exclusions_are_case_insensitive(engine):
    snapshot = SchemaService(engine, "main", excluded_tables=["SUGGESTIONS"]).snapshot()
    assert [table.name for table in snapshot.tables] == ["clientes"]


def test_relationship_to_internal_table_is_not_exposed():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    Table(
        "suggestions",
        metadata,
        Column("id", Integer, primary_key=True),
    )
    Table(
        "pedidos",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("suggestion_id", ForeignKey("suggestions.id")),
    )
    metadata.create_all(engine)

    relationships = TableDataService(engine, "main").relationships("pedidos")
    assert relationships.outbound == []

    snapshot = SchemaService(engine, "main").snapshot()
    pedidos = next(table for table in snapshot.tables if table.name == "pedidos")
    assert pedidos.foreign_keys == []
