from app.schemas.schema import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    SchemaSnapshot,
    TableInfo,
)
from app.services.advisor_service import AdvisorService


def test_missing_primary_key_is_reported():
    table = TableInfo(
        name="events",
        schema="public",
        columns=[ColumnInfo(name="description", type="TEXT", nullable=True)],
        primary_key=[],
        foreign_keys=[],
        indexes=[],
    )
    report = AdvisorService().analyze(
        SchemaSnapshot(database="postgres", schema="public", tables=[table])
    )
    assert report.tables_analyzed == 1
    assert any(r.category == "primary_key" for r in report.recommendations)


def _child_table(indexes: list[IndexInfo]) -> TableInfo:
    return TableInfo(
        name="child",
        schema="public",
        columns=[ColumnInfo(name="parent_id", type="INTEGER", nullable=False)],
        primary_key=[],
        foreign_keys=[
            ForeignKeyInfo(
                constrained_columns=["parent_id"],
                referred_table="parent",
                referred_schema="public",
                referred_columns=["id"],
            )
        ],
        indexes=indexes,
    )


def _report_for_child(indexes: list[IndexInfo]):
    parent = TableInfo(
        name="parent",
        schema="public",
        columns=[ColumnInfo(name="id", type="INTEGER", nullable=False, is_primary_key=True)],
        primary_key=["id"],
        foreign_keys=[],
        indexes=[],
    )
    return AdvisorService().analyze(
        SchemaSnapshot(
            database="postgres",
            schema="public",
            tables=[parent, _child_table(indexes)],
        )
    )


def test_foreign_key_without_index_suggests_postgres_sql():
    report = _report_for_child([])
    item = next(r for r in report.recommendations if r.category == "index")
    assert "CREATE INDEX" in item.suggested_sql
    assert '"public"."child"' in item.suggested_sql
    assert "`" not in item.suggested_sql


def test_composite_index_does_not_hide_unindexed_foreign_key():
    report = _report_for_child([
        IndexInfo(name="idx_other_parent", column_names=["other_id", "parent_id"], unique=False)
    ])
    assert any(r.category == "index" for r in report.recommendations)


def test_index_starting_with_foreign_key_suppresses_recommendation():
    report = _report_for_child([
        IndexInfo(name="idx_parent", column_names=["parent_id", "other_id"], unique=False)
    ])
    assert not any(r.category == "index" for r in report.recommendations)


def test_cross_schema_foreign_key_is_not_reported_missing_from_snapshot():
    child = TableInfo(
        name="child",
        schema="public",
        columns=[ColumnInfo(name="parent_id", type="INTEGER", nullable=False)],
        primary_key=[],
        foreign_keys=[
            ForeignKeyInfo(
                constrained_columns=["parent_id"],
                referred_table="parent",
                referred_schema="shared",
                referred_columns=["id"],
            )
        ],
        indexes=[IndexInfo(name="idx_parent", column_names=["parent_id"], unique=False)],
    )
    report = AdvisorService().analyze(
        SchemaSnapshot(database="postgres", schema="public", tables=[child])
    )
    assert not any(r.category == "foreign_key" for r in report.recommendations)
