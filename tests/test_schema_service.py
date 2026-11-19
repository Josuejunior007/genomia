from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
)

from app.services.schema_service import SchemaService


def build_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    parent = Table(
        "parent",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(50), nullable=False),
    )
    child = Table(
        "child",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", ForeignKey("parent.id"), nullable=False),
        Column("code", String(10), nullable=True),
    )
    Index("ix_child_code", child.c.code)
    metadata.create_all(engine)
    return engine


def test_single_table_reflection_returns_columns_keys_and_indexes():
    service = SchemaService(build_engine(), "main")

    table = service.table("child")

    assert table is not None
    assert table.name == "child"
    assert table.schema == "main"
    assert [column.name for column in table.columns] == ["id", "parent_id", "code"]
    assert table.primary_key == ["id"]
    assert table.columns[0].is_primary_key is True
    assert len(table.foreign_keys) == 1
    assert table.foreign_keys[0].referred_table == "parent"
    assert table.foreign_keys[0].constrained_columns == ["parent_id"]
    assert [index.name for index in table.indexes] == ["ix_child_code"]


def test_single_table_reflection_returns_none_for_unknown_table():
    service = SchemaService(build_engine(), "main")
    assert service.table("does_not_exist") is None


def test_snapshot_still_lists_every_table():
    snapshot = SchemaService(build_engine(), "main").snapshot()
    assert sorted(table.name for table in snapshot.tables) == ["child", "parent"]
