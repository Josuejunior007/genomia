"""Conexão e ciclo de vida do banco interno do GenomAI.

Este módulo é deliberadamente independente de ``app.db.session`` (banco
analisado). As duas conexões nunca compartilham engine, sessão ou credenciais.
O objetivo é impedir que sugestões e auditorias sejam confundidas com os dados
que a IA pode analisar.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, make_url, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base

# Importa os modelos para registrar as tabelas no metadata antes do create_all.
from app import models  # noqa: F401  (side effect: registra tabelas)


def _resolve_app_database_url(raw_url: str) -> URL:
    """Resolve caminhos SQLite relativos à raiz do projeto.

    Assim o arquivo de desenvolvimento fica sempre ao lado do projeto,
    independentemente do diretório de trabalho usado pelo uvicorn/PyCharm.
    """
    url = make_url(raw_url)
    if url.drivername.startswith("sqlite") and url.database not in (None, ":memory:"):
        database_path = Path(url.database)
        if not database_path.is_absolute():
            database_path = (Path(__file__).resolve().parents[2] / database_path).resolve()
            url = url.set(database=str(database_path))
    return url


app_database_url = _resolve_app_database_url(settings.app_database_url)
if app_database_url.drivername.startswith("sqlite"):
    _connect_args: dict[str, Any] = {"check_same_thread": False}
elif app_database_url.drivername.startswith("postgresql"):
    _connect_args = {"connect_timeout": 5}
else:
    _connect_args = {}
app_engine = create_engine(
    app_database_url,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
AppSessionLocal = sessionmaker(bind=app_engine, autoflush=False, autocommit=False)

_ensured = False
_ensure_lock = threading.Lock()

# Colunas adicionadas depois da primeira versão do MVP. A migração é idempotente
# e roda no startup/lazy para preservar bancos SQLite já existentes.
_SQLITE_COLUMN_MIGRATIONS: dict[str, str] = {
    "column_name": "VARCHAR(255)",
    "suggested_sql": "TEXT",
    "version": "INTEGER NOT NULL DEFAULT 1",
    "previous_status": "VARCHAR(20)",
    "reviewed_by": "VARCHAR(80)",
    "edited_by": "VARCHAR(80)",
    "updated_at": "DATETIME",
    "applied_at": "DATETIME",
    "applied_by": "VARCHAR(80)",
    "apply_error": "TEXT",
}


def _quoted_schema(engine: Engine) -> str:
    """Schema interno já citado conforme o dialeto (PostgreSQL)."""
    return engine.dialect.identifier_preparer.quote_schema(settings.app_db_schema)


def _migrate_sqlite(engine: Engine) -> None:
    """Adiciona colunas novas e cria a revisão inicial de sugestões antigas."""
    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(suggestions)").fetchall()
        }
        if not existing:
            return
        for column, ddl in _SQLITE_COLUMN_MIGRATIONS.items():
            if column not in existing:
                connection.exec_driver_sql(
                    f"ALTER TABLE suggestions ADD COLUMN {column} {ddl}"
                )
        # Sugestões criadas antes do histórico existente ganham uma revisão
        # inicial. A cláusula NOT EXISTS mantém a operação idempotente.
        connection.exec_driver_sql(
            """
            INSERT INTO suggestion_revisions (
                suggestion_id, version, table_name, kind, column_name,
                description, confidence, status, rationale, suggested_sql,
                edited_by, comment, created_at
            )
            SELECT
                s.id, COALESCE(s.version, 1), s.table_name, s.kind, s.column_name,
                s.description, s.confidence, s.status, s.rationale, s.suggested_sql,
                COALESCE(s.edited_by, 'migracao'),
                'Revisão inicial criada na migração do banco local',
                COALESCE(s.created_at, CURRENT_TIMESTAMP)
            FROM suggestions AS s
            WHERE NOT EXISTS (
                SELECT 1 FROM suggestion_revisions AS r
                WHERE r.suggestion_id = s.id
            )
            """
        )


def ensure_app_store(engine: Engine | None = None) -> None:
    """Cria schema/tabelas e aplica migrações leves do banco interno.

    Em PostgreSQL o schema ``APP_DB_SCHEMA`` é criado quando
    ``APP_DB_AUTO_CREATE=true``. Em produção, o ideal é provisionar o schema e
    a role de escrita com ``scripts/app_store_postgres.sql`` e
    ``scripts/provision_app_store_role.sql``, mantendo a aplicação sem
    permissão de DDL estrutural.
    """
    global _ensured
    target = engine or app_engine
    with _ensure_lock:
        if _ensured:
            return

        dialect = target.dialect.name
        if dialect == "postgresql" and settings.app_db_auto_create:
            schema = _quoted_schema(target)
            try:
                with target.begin() as connection:
                    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            except Exception as exc:  # pragma: no cover - depende do provedor
                raise RuntimeError(
                    "Não foi possível criar o schema interno "
                    f"{settings.app_db_schema!r}. Execute scripts/app_store_postgres.sql "
                    "com uma role administrativa ou defina APP_DB_AUTO_CREATE=false "
                    "após provisionar o schema. Detalhe: " + str(exc)
                ) from exc

        if dialect == "postgresql" and not settings.app_db_auto_create:
            # Em produção não emitimos DDL. Apenas conferimos se o schema foi
            # provisionado; caso contrário, falhamos com instrução clara.
            inspector = inspect(target)
            existing = set(inspector.get_table_names(schema=settings.app_db_schema))
            missing = [
                table.name
                for table in Base.metadata.sorted_tables
                if table.name not in existing
            ]
            if missing:
                raise RuntimeError(
                    "Tabelas internas ausentes em "
                    f"{settings.app_db_schema!r}: {', '.join(missing)}. "
                    "Execute scripts/app_store_postgres.sql antes de iniciar a API "
                    "ou defina APP_DB_AUTO_CREATE=true (somente em dev)."
                )
            missing_columns: list[str] = []
            for table in Base.metadata.sorted_tables:
                columns = {
                    column["name"]
                    for column in inspector.get_columns(
                        table.name, schema=settings.app_db_schema
                    )
                }
                for column in table.columns:
                    if column.name not in columns:
                        missing_columns.append(f"{table.name}.{column.name}")
            if missing_columns:
                raise RuntimeError(
                    "Colunas internas ausentes: "
                    + ", ".join(missing_columns)
                    + ". Aplique a migração correspondente em "
                    "scripts/app_store_postgres.sql."
                )
        else:
            Base.metadata.create_all(bind=target)

        if dialect == "sqlite":
            _migrate_sqlite(target)

        _ensured = True


def reset_app_store_state() -> None:
    """Reinicia o cache de inicialização (usado em testes)."""
    global _ensured
    with _ensure_lock:
        _ensured = False


def get_app_db():
    """Dependency do FastAPI que entrega uma sessão do banco interno."""
    ensure_app_store()
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _same_database(left: URL, right: URL) -> bool:
    """Compara host/porta/banco sem expor credenciais em mensagens."""
    return (
        (left.host or "").casefold() == (right.host or "").casefold()
        and (left.port or 0) == (right.port or 0)
        and (left.database or "").casefold() == (right.database or "").casefold()
    )


def app_store_info() -> dict[str, Any]:
    """Descreve o armazenamento interno para o endpoint de diagnóstico."""
    url = app_engine.url
    backend = url.get_backend_name()
    schema = settings.app_store_schema
    info: dict[str, Any] = {
        "backend": backend,
        "schema": schema,
        "persistent": True,
        "remote": backend != "sqlite",
        "location": (
            "arquivo local no servidor (desenvolvimento)"
            if backend == "sqlite"
            else "servidor de banco de dados"
        ),
        "isolation": (
            "Banco/schema próprio do GenomAI; nunca é lido pela análise de IA."
        ),
    }
    try:
        tables = inspect(app_engine).get_table_names(schema=schema)
        info["tables"] = sorted(tables)
        info["available"] = True
    except Exception as exc:  # pragma: no cover - depende do provedor
        info["tables"] = []
        info["available"] = False
        info["error"] = type(exc).__name__
    return info


def validate_store_isolation(analyzed_engine: Engine | None = None) -> list[str]:
    """Valida que o armazenamento interno não se mistura ao banco analisado.

    Retorna avisos não fatais. Levanta ``RuntimeError`` quando a configuração é
    insegura (por exemplo, o mesmo schema do banco analisado ou a mesma role de
    leitura sendo usada para escrever sugestões).
    """
    from app.db.session import engine as analyzed_engine_default

    analyzed = analyzed_engine or analyzed_engine_default
    warnings: list[str] = []

    if app_engine.dialect.name == "sqlite":
        warnings.append(
            "Armazenamento interno em SQLite local. Para produção, configure "
            "APP_DATABASE_URL para PostgreSQL com schema próprio."
        )
        if settings.app_store_require_remote:
            raise RuntimeError(
                "APP_STORE_REQUIRE_REMOTE=true exige um banco interno remoto; "
                "APP_DATABASE_URL atual usa SQLite."
            )
        return warnings

    if settings.app_db_schema.casefold() == settings.db_schema.casefold():
        raise RuntimeError(
            "O schema do armazenamento interno (APP_DB_SCHEMA) não pode ser "
            "igual ao schema analisado (DB_SCHEMA). Use um schema dedicado, "
            "por exemplo 'genomai_app'."
        )

    app_url = app_engine.url
    analyzed_url = analyzed.url
    if app_engine.dialect.name == analyzed.dialect.name and _same_database(app_url, analyzed_url):
        if (app_url.username or "") == (analyzed_url.username or ""):
            raise RuntimeError(
                "O banco interno e o banco analisado usam a mesma role. "
                "Crie uma role de escrita dedicada para APP_DATABASE_URL."
            )
        warnings.append(
            "Armazenamento interno no mesmo servidor do banco analisado, mas em "
            "schema e role diferentes. Isolamento lógico garantido por schema."
        )
    return warnings
