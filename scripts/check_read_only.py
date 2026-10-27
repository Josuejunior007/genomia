"""CLI to validate the configured PostgreSQL runtime role."""

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.permissions import validate_read_only


def main() -> int:
    engine = create_engine(
        settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
    )
    try:
        validate_read_only(engine, settings.db_schema)
        print(f"OK: permissões read-only confirmadas para o schema {settings.db_schema}.")
        return 0
    except (SQLAlchemyError, RuntimeError) as exc:
        # Driver errors can include infrastructure details; keep output credential-safe.
        message = str(exc) if isinstance(exc, RuntimeError) else "conexão PostgreSQL indisponível."
        print(f"Falha na validação read-only: {message}")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
