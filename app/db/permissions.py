"""Fail-closed validation of PostgreSQL runtime permissions."""

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


CHECK_SQL = text("""
SELECT
    r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
        OR r.rolreplication OR r.rolbypassrls AS elevated_role,
    has_schema_privilege(current_user, :schema, 'USAGE') AS schema_usage,
    has_schema_privilege(current_user, :schema, 'CREATE') AS schema_create,
    has_database_privilege(current_user, current_database(), 'CREATE') AS database_create,
    EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = :schema
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND (
              has_table_privilege(current_user, c.oid, 'INSERT')
              OR has_table_privilege(current_user, c.oid, 'UPDATE')
              OR has_table_privilege(current_user, c.oid, 'DELETE')
              OR has_table_privilege(current_user, c.oid, 'TRUNCATE')
              OR has_table_privilege(current_user, c.oid, 'TRIGGER')
              OR has_table_privilege(current_user, c.oid, 'REFERENCES')
              OR has_any_column_privilege(current_user, c.oid, 'INSERT')
              OR has_any_column_privilege(current_user, c.oid, 'UPDATE')
          )
    ) AS has_write_access
""")


def validate_read_only(connection: Connection | Engine, schema: str) -> None:
    """Raise RuntimeError unless the active PostgreSQL role is read-only."""
    if connection.dialect.name != "postgresql":
        raise RuntimeError("A validação de permissões requer PostgreSQL.")
    with connection.connect() if isinstance(connection, Engine) else _existing(connection) as conn:
        result = conn.execute(CHECK_SQL, {"schema": schema}).mappings().one()
        conn.execute(text("SELECT table_name FROM information_schema.tables LIMIT 0"))
    problems = []
    if result["elevated_role"]:
        problems.append("atributo administrativo")
    if not result["schema_usage"]:
        problems.append(f"falta USAGE no schema {schema!r}")
    if result["schema_create"] or result["database_create"]:
        problems.append("permissão para criar objetos")
    if result["has_write_access"]:
        problems.append(f"permissão de escrita no schema {schema!r}")
    if problems:
        raise RuntimeError("Permissões do PostgreSQL não são somente leitura: " + "; ".join(problems))


class _existing:
    """Context manager that leaves a caller-owned connection open."""

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_):
        return False
