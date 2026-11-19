from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
)

from app.services.table_data_service import (
    TableDataService,
    TableNotFoundError,
    jsonable,
)


@pytest.fixture()
def engine():
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
        Column("note", String(50), nullable=True),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(insert(parent), [{"id": 2, "name": "beta"}, {"id": 1, "name": "alfa"}])
        connection.execute(
            insert(child),
            [
                {"id": 10, "parent_id": 1, "note": "primeiro"},
                {"id": 11, "parent_id": 1, "note": None},
                {"id": 12, "parent_id": 2, "note": "terceiro"},
            ],
        )
    return engine


def service(engine) -> TableDataService:
    return TableDataService(engine, "main", default_limit=2, max_limit=50)


def test_rows_are_paginated_and_ordered_by_primary_key(engine):
    page = service(engine).rows("parent", limit=1, offset=1)

    assert page.table == "parent"
    assert page.total == 2
    assert page.limit == 1
    assert page.offset == 1
    assert [row["id"] for row in page.rows] == [2]
    assert [column.name for column in page.columns] == ["id", "name"]
    assert page.columns[0].is_primary_key is True


def test_rows_keep_null_values(engine):
    page = service(engine).rows("child", limit=50, offset=0)
    assert page.total == 3
    assert page.rows[1]["note"] is None


def test_rows_reject_limit_outside_the_allowed_range(engine):
    with pytest.raises(ValueError):
        service(engine).rows("parent", limit=0)
    with pytest.raises(ValueError):
        service(engine).rows("parent", limit=500)
    with pytest.raises(ValueError):
        service(engine).rows("parent", offset=-1)


def test_unknown_table_raises_not_found(engine):
    with pytest.raises(TableNotFoundError):
        service(engine).rows("does_not_exist")
    with pytest.raises(TableNotFoundError):
        service(engine).relationships("does_not_exist")


def test_relationships_include_outbound_and_inbound_keys(engine):
    child = service(engine).relationships("child")
    parent = service(engine).relationships("parent")

    assert len(child.outbound) == 1
    assert child.inbound == []
    assert child.outbound[0].source_table == "child"
    assert child.outbound[0].source_columns == ["parent_id"]
    assert child.outbound[0].target_table == "parent"
    assert child.outbound[0].target_columns == ["id"]

    assert parent.outbound == []
    assert len(parent.inbound) == 1
    assert parent.inbound[0].source_table == "child"
    assert parent.inbound[0].source_columns == ["parent_id"]


def test_jsonable_converts_database_types():
    identifier = UUID("12345678-1234-5678-1234-567812345678")
    assert jsonable(None) is None
    assert jsonable(True) is True
    assert jsonable(12) == 12
    assert jsonable(Decimal("10.50")) == 10.5
    assert jsonable(Decimal("NaN")) == "NaN"
    assert jsonable(float("inf")) == "inf"
    assert jsonable(datetime(2026, 11, 19, 13, 56, 45)) == "2026-11-19T13:56:45"
    assert jsonable(date(2026, 11, 19)) == "2026-11-19"
    assert jsonable(identifier) == "12345678-1234-5678-1234-567812345678"
    assert jsonable(b"\x01\xab") == "01ab"
    assert jsonable({"when": date(2026, 11, 19)}) == {"when": "2026-11-19"}
    assert jsonable([Decimal("1.5")]) == [1.5]
