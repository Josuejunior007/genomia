from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from app.schemas.schema import ColumnInfo, ForeignKeyInfo, IndexInfo, SchemaSnapshot, TableInfo

class SchemaService:
    def __init__(self, engine: Engine, schema_name: str = "public"):
        self.engine = engine
        self.schema_name = schema_name

    def table(self, table_name: str) -> TableInfo | None:
        """Reflect a single table instead of the whole schema."""
        inspector = inspect(self.engine)
        if table_name not in inspector.get_table_names(schema=self.schema_name):
            return None
        return self._build_table(inspector, table_name)

    def _build_table(self, inspector, table_name: str) -> TableInfo:
        columns = [ColumnInfo(
            name=c["name"], type=str(c["type"]), nullable=c.get("nullable", True),
            default=None if c.get("default") is None else str(c["default"]),
            is_primary_key=False
        ) for c in inspector.get_columns(table_name, schema=self.schema_name)]
        pk = inspector.get_pk_constraint(table_name, schema=self.schema_name).get("constrained_columns") or []
        pk_set = set(pk)
        for col in columns:
            col.is_primary_key = col.name in pk_set
        fks = [ForeignKeyInfo(
            constrained_columns=f.get("constrained_columns") or [],
            referred_table=f.get("referred_table") or "",
            referred_schema=f.get("referred_schema") or self.schema_name,
            referred_columns=f.get("referred_columns") or []
        ) for f in inspector.get_foreign_keys(table_name, schema=self.schema_name)]
        indexes = [IndexInfo(
            name=i.get("name") or "", column_names=i.get("column_names") or [],
            unique=bool(i.get("unique"))
        ) for i in inspector.get_indexes(table_name, schema=self.schema_name)]
        return TableInfo(name=table_name, schema=self.schema_name, columns=columns,
                         primary_key=pk, foreign_keys=fks, indexes=indexes)

    def snapshot(self) -> SchemaSnapshot:
        inspector = inspect(self.engine)
        tables = [self._build_table(inspector, table_name)
                  for table_name in inspector.get_table_names(schema=self.schema_name)]
        return SchemaSnapshot(database=self.engine.url.database or "postgres",
                              schema=self.schema_name, tables=tables)
