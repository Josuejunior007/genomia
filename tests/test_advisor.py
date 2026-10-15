from app.schemas.schema import ColumnInfo, ForeignKeyInfo, IndexInfo, SchemaSnapshot, TableInfo
from app.services.advisor_service import AdvisorService

def test_missing_primary_key_is_reported():
    table = TableInfo(name="events", schema="public", columns=[
        ColumnInfo(name="description", type="TEXT", nullable=True)
    ], primary_key=[], foreign_keys=[], indexes=[])
    report = AdvisorService().analyze(SchemaSnapshot(database="postgres", schema="public", tables=[table]))
    assert report.tables_analyzed == 1
    assert any(r.category == "primary_key" for r in report.recommendations)

def test_foreign_key_without_index_suggests_postgres_sql():
    parent = TableInfo(name="parent", schema="public", columns=[
        ColumnInfo(name="id", type="INTEGER", nullable=False, is_primary_key=True)
    ], primary_key=["id"], foreign_keys=[], indexes=[])
    child = TableInfo(name="child", schema="public", columns=[
        ColumnInfo(name="parent_id", type="INTEGER", nullable=False)
    ], primary_key=[], foreign_keys=[
        ForeignKeyInfo(constrained_columns=["parent_id"], referred_table="parent",
                       referred_schema="public", referred_columns=["id"])
    ], indexes=[])
    report = AdvisorService().analyze(SchemaSnapshot(database="postgres", schema="public", tables=[parent, child]))
    item = next(r for r in report.recommendations if r.category == "index")
    assert 'CREATE INDEX' in item.suggested_sql
    assert '`' not in item.suggested_sql
