"""Validate that the configured PostgreSQL runtime role is read-only."""

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings


CHECK_SQL = text("""
SELECT
    r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
        OR r.rolreplication OR r.rolbypassrls AS elevated_role,
    has_schema_privilege(current_user, :schema, 'USAGE') AS schema_usage,
    has_schema_privilege(current_user, :schema, 'CREATE') AS schema_create,
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
              OR has_any_column_privilege(current_user, c.oid, 'INSERT')
              OR has_any_column_privilege(current_user, c.oid, 'UPDATE')
          )
    ) AS has_write_access
""")


def main() -> int:
    engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            if connection.dialect.name != "postgresql":
                raise RuntimeError("A validação de permissões requer PostgreSQL.")
            result = connection.execute(CHECK_SQL, {"schema": settings.db_schema}).mappings().one()
            # Confirma também que o runtime consegue consultar information_schema.
            connection.execute(text("SELECT table_name FROM information_schema.tables LIMIT 0"))
            problems = []
            if result["elevated_role"]:
                problems.append("a role possui atributo administrativo")
            if not result["schema_usage"]:
                problems.append(f"falta USAGE no schema {settings.db_schema!r}")
            if result["schema_create"]:
                problems.append(f"a role pode criar objetos no schema {settings.db_schema!r}")
            if result["has_write_access"]:
                problems.append(f"a role possui privilégio de escrita em objetos de {settings.db_schema!r}")
            if problems:
                raise RuntimeError("Permissões não são somente leitura: " + "; ".join(problems))
            print(f"OK: role {connection.exec_driver_sql('SELECT current_user').scalar_one()} validada como read-only em {settings.db_schema}.")
            return 0
    except (SQLAlchemyError, RuntimeError) as exc:
        print(f"Falha na validação read-only: {exc}")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
