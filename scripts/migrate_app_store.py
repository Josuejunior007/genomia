"""Migra sugestões legadas para o armazenamento interno configurado.

Casos suportados:

* SQLite antigo (``genomai_app.db``) -> ``APP_DATABASE_URL``.
* Tabela legada ``public.suggestions`` no PostgreSQL/Supabase (somente leitura)
  -> ``APP_DATABASE_URL``.

O script é idempotente por uma chave lógica (tabela + tipo + descrição) e não
copia dados de atendimentos: apenas sugestões e metadados de revisão. Nenhuma
linha do banco analisado é lida.

Exemplos::

    # Prévia, sem gravar
    python -m scripts.migrate_app_store --sqlite ./genomai_app.db --dry-run

    # Migrar SQLite local para o PostgreSQL interno configurado
    python -m scripts.migrate_app_store --sqlite ./genomai_app.db

    # Migrar a tabela legada public.suggestions do Supabase
    python -m scripts.migrate_app_store --postgres-url "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, select, text

from app.core.config import settings
from app.db.app_session import AppSessionLocal, app_engine, app_store_info, ensure_app_store
from app.models.audit import SuggestionRevision
from app.models.suggestion import Suggestion

VALID_STATUSES = {"pending", "approved", "rejected", "partially_approved"}


def _parse_datetime(value: Any) -> datetime | None:
    """Converte strings de data de SQLite/PostgreSQL em ``datetime``."""
    if value is None or isinstance(value, datetime):
        return value
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        return datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _row_to_suggestion(row: dict[str, Any]) -> dict[str, Any]:
    """Normaliza nomes de colunas das duas origens legadas."""
    table_name = row.get("table_name") or row.get("table") or ""
    status = str(row.get("status") or "pending").strip().lower()
    if status not in VALID_STATUSES:
        status = "pending"
    return {
        "table_name": str(table_name),
        "kind": str(row.get("kind") or "review"),
        "column_name": row.get("column_name"),
        "description": str(row.get("description") or ""),
        "confidence": float(row.get("confidence") or 0.0),
        "status": status,
        "rationale": str(row.get("rationale") or ""),
        "suggested_sql": row.get("suggested_sql"),
        "review_comment": str(row.get("review_comment") or ""),
        "reviewed_by": row.get("reviewed_by"),
        "created_at": _parse_datetime(row.get("created_at")),
        "reviewed_at": _parse_datetime(row.get("reviewed_at")),
    }


def _read_sqlite(path: Path) -> list[dict[str, Any]]:
    """Lê a tabela ``suggestions`` de um arquivo SQLite legado."""
    if not path.exists():
        raise FileNotFoundError(f"SQLite não encontrado: {path}")
    engine = create_engine(f"sqlite:///{path}")
    try:
        if "suggestions" not in inspect(engine).get_table_names():
            raise RuntimeError(f"O arquivo {path} não contém a tabela suggestions.")
        with engine.connect() as connection:
            return [
                dict(row._mapping)
                for row in connection.execute(text("SELECT * FROM suggestions"))
            ]
    finally:
        engine.dispose()


def _read_postgres(url: str) -> list[dict[str, Any]]:
    """Lê a tabela legada ``public.suggestions`` sem alterá-la."""
    engine = create_engine(url, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'suggestions'"
                )
            ).scalar()
            if not exists:
                raise RuntimeError("Tabela public.suggestions não encontrada.")
            return [
                dict(row._mapping)
                for row in connection.execute(text("SELECT * FROM public.suggestions"))
            ]
    finally:
        engine.dispose()


def _target_is_same_sqlite(source: Path) -> bool:
    """Evita migrar um arquivo SQLite para ele mesmo."""
    if not settings.app_database_url.startswith("sqlite"):
        return False
    target = app_engine.url.database
    if not target:
        return False
    return Path(target).resolve() == source.resolve()


def _existing_keys(session) -> set[tuple[str, str, str]]:
    """Chave lógica para idempotência da migração."""
    rows = session.execute(
        select(Suggestion.table_name, Suggestion.kind, Suggestion.description)
    ).all()
    return {
        (str(row[0]).casefold(), str(row[1]).casefold(), str(row[2]).casefold())
        for row in rows
    }


def migrate(rows: list[dict[str, Any]], dry_run: bool = False) -> dict[str, int]:
    """Insere as sugestões normalizadas no armazenamento interno."""
    ensure_app_store()
    session = AppSessionLocal()
    result = {"read": len(rows), "inserted": 0, "skipped": 0, "invalid": 0}
    try:
        existing = _existing_keys(session)
        for raw in rows:
            item = _row_to_suggestion(raw)
            if not item["table_name"] or not item["description"]:
                result["invalid"] += 1
                continue
            key = (
                item["table_name"].casefold(),
                item["kind"].casefold(),
                item["description"].casefold(),
            )
            if key in existing:
                result["skipped"] += 1
                continue
            existing.add(key)
            result["inserted"] += 1
            if dry_run:
                continue
            suggestion = Suggestion(
                table_name=item["table_name"][:255],
                kind=item["kind"][:40],
                column_name=item["column_name"],
                description=item["description"][:5000],
                confidence=min(1.0, max(0.0, item["confidence"])),
                status=item["status"],
                rationale=item["rationale"][:5000],
                suggested_sql=item["suggested_sql"],
                review_comment=item["review_comment"][:1000],
                reviewed_by=item["reviewed_by"],
                reviewed_at=item["reviewed_at"],
            )
            if item["created_at"] is not None:
                suggestion.created_at = item["created_at"]
            session.add(suggestion)
            session.flush()
            session.add(
                SuggestionRevision(
                    suggestion_id=suggestion.id,
                    version=1,
                    table_name=suggestion.table_name,
                    kind=suggestion.kind,
                    column_name=suggestion.column_name,
                    description=suggestion.description,
                    confidence=suggestion.confidence,
                    status=suggestion.status,
                    rationale=suggestion.rationale,
                    suggested_sql=suggestion.suggested_sql,
                    edited_by="migracao",
                    comment="Migração do armazenamento legado",
                )
            )
        if dry_run:
            session.rollback()
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI da migração."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, help="Caminho do SQLite legado.")
    parser.add_argument(
        "--postgres-url",
        help="URL read-only do PostgreSQL com a tabela legada public.suggestions.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Não grava nada.")
    args = parser.parse_args(argv)

    sources = sum(bool(value) for value in (args.sqlite, args.postgres_url))
    if sources != 1:
        parser.error("Informe exatamente uma origem: --sqlite ou --postgres-url.")

    try:
        if args.sqlite:
            source_path = args.sqlite.resolve()
            if _target_is_same_sqlite(source_path):
                print("Origem e destino são o mesmo SQLite; nada a migrar.")
                return 0
            rows = _read_sqlite(source_path)
            origin = str(source_path)
        else:
            rows = _read_postgres(args.postgres_url or "")
            origin = "postgresql:public.suggestions"
        target = app_store_info()
        print(
            f"Origem: {origin}\nDestino: {target.get('backend')} "
            f"schema={target.get('schema')} tabelas={target.get('tables')}"
        )
        result = migrate(rows, dry_run=args.dry_run)
        print(
            "Resultado: "
            f"lidas={result['read']} inseridas={result['inserted']} "
            f"ignoradas={result['skipped']} inválidas={result['invalid']}"
            + (" (dry-run; nada foi gravado)" if args.dry_run else "")
        )
        return 0
    except Exception as exc:  # mensagem segura, sem credenciais
        print(f"Falha na migração: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
