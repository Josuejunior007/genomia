"""Fail-closed validation of PostgreSQL runtime permissions."""

from sqlalchemy import text
from sqlalchemy.engine import Engine


CHECK_SQL = text("""
SELECT
    r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
        OR r.rolreplication OR r.rolbypassrls AS elevated_role,
    EXISTS (
        SELECT 1 FROM pg_auth_members m WHERE m.member = r.oid
    ) AS has_memberships,
    has_schema_privilege(current_user, :schema, 'USAGE') AS schema_usage,
    has_schema_privilege(current_user, :schema, 'CREATE') AS schema_create,
    has_database_privilege(current_user, current_database(), 'CREATE') AS database_create,
    EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = :schema
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND NOT has_table_privilege(current_user, c.oid, 'SELECT')
    ) AS has_unreadable_tables,
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
FROM pg_roles r
WHERE r.rolname = current_user
""")


def validate_read_only(engine: Engine, schema: str) -> None:
    """Raise RuntimeError unless the active PostgreSQL role is read-only."""
    if engine.dialect.name != "postgresql":
        raise RuntimeError("A validação de permissões requer PostgreSQL.")
    with engine.connect() as connection:
        result = connection.execute(CHECK_SQL, {"schema": schema}).mappings().one()
        connection.execute(text("SELECT table_name FROM information_schema.tables LIMIT 0"))
    problems = []
    if result["elevated_role"]:
        problems.append("atributo administrativo")
    if result["has_memberships"]:
        problems.append("membership em outra role")
    if not result["schema_usage"]:
        problems.append(f"falta USAGE no schema {schema!r}")
    if result["schema_create"] or result["database_create"]:
        problems.append("permissão para criar objetos")
    if result["has_unreadable_tables"]:
        problems.append(f"falta SELECT em tabelas do schema {schema!r}")
    if result["has_write_access"]:
        problems.append(f"permissão de escrita no schema {schema!r}")
    if problems:
        raise RuntimeError("Permissões do PostgreSQL não são somente leitura: " + "; ".join(problems))
