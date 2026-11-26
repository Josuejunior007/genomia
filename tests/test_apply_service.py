"""Testes da aplicação controlada de mudanças (com SQLite como alvo de teste)."""

from __future__ import annotations

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models.suggestion import Suggestion
from app.services.change_apply_service import (
    ApplyBlockedError,
    ApplyContext,
    ChangeApplyService,
)


@pytest.fixture()
def analyzed_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    Table(
        "clientes",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("codigo", String(20), nullable=True),
        Column("outra", String(20), nullable=True),
    )
    metadata.create_all(engine)
    return engine


@pytest.fixture()
def app_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def make_suggestion(
    db: Session,
    *,
    kind: str = "index",
    column_name: str | None = "codigo",
    status: str = "approved",
) -> Suggestion:
    item = Suggestion(
        table_name="clientes",
        kind=kind,
        column_name=column_name,
        description="Documentar a tabela de clientes.",
        confidence=0.9,
        rationale="Metadados indicam ausência de índice.",
        status=status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def service(db: Session, analyzed_engine, write_engine=None):
    return ChangeApplyService(
        ApplyContext(
            app_db=db,
            analyzed_engine=analyzed_engine,
            write_engine=write_engine or analyzed_engine,
            persona="desenvolvedor",
            schema="main",
        )
    )


def test_preview_generates_server_side_index_sql(app_db, analyzed_engine, monkeypatch):
    monkeypatch.setattr(settings, "db_write_enabled", True)
    monkeypatch.setattr(settings, "write_database_url", None)
    item = make_suggestion(app_db)

    preview = service(app_db, analyzed_engine).preview(item)

    assert preview.can_apply is True
    assert preview.sql and "CREATE INDEX" in preview.sql
    assert '"clientes"' in preview.sql
    assert '"codigo"' in preview.sql
    assert preview.blockers == []


def test_apply_creates_index_and_records_audit(app_db, analyzed_engine, monkeypatch):
    monkeypatch.setattr(settings, "db_write_enabled", True)
    monkeypatch.setattr(settings, "write_database_url", None)
    item = make_suggestion(app_db)

    result = service(app_db, analyzed_engine).apply(item)

    assert result.success is True
    assert result.log_id is not None
    indexes = inspect(analyzed_engine).get_indexes("clientes")
    assert any("codigo" in index["column_names"] for index in indexes)
    assert item.applied_at is not None
    assert item.applied_by == "desenvolvedor"


def test_apply_blocks_when_write_disabled(app_db, analyzed_engine, monkeypatch):
    monkeypatch.setattr(settings, "db_write_enabled", False)
    item = make_suggestion(app_db)

    preview = service(app_db, analyzed_engine).preview(item)

    assert preview.can_apply is False
    assert any("DB_WRITE_ENABLED" in blocker for blocker in preview.blockers)
    with pytest.raises(ApplyBlockedError):
        service(app_db, analyzed_engine).apply(item)


def test_apply_blocks_unapproved_suggestion(app_db, analyzed_engine, monkeypatch):
    monkeypatch.setattr(settings, "db_write_enabled", True)
    item = make_suggestion(app_db, status="pending")

    preview = service(app_db, analyzed_engine).preview(item)

    assert preview.can_apply is False
    assert any("aprovada" in blocker for blocker in preview.blockers)


def test_apply_blocks_duplicate_index(app_db, analyzed_engine, monkeypatch):
    monkeypatch.setattr(settings, "db_write_enabled", True)
    with analyzed_engine.begin() as connection:
        connection.exec_driver_sql("CREATE INDEX ix_clientes_codigo ON clientes (codigo)")
    item = make_suggestion(app_db)

    preview = service(app_db, analyzed_engine).preview(item)

    assert preview.can_apply is False
    assert any("redundante" in blocker for blocker in preview.blockers)


def test_apply_blocks_unsupported_kind(app_db, analyzed_engine, monkeypatch):
    monkeypatch.setattr(settings, "db_write_enabled", True)
    item = make_suggestion(app_db, kind="integrity")

    preview = service(app_db, analyzed_engine).preview(item)

    assert preview.can_apply is False
    assert any("documentation" in blocker for blocker in preview.blockers)


def test_comment_apply_is_blocked_on_non_postgres(app_db, analyzed_engine, monkeypatch):
    monkeypatch.setattr(settings, "db_write_enabled", True)
    item = make_suggestion(app_db, kind="documentation", column_name=None)

    preview = service(app_db, analyzed_engine).preview(item)

    assert preview.can_apply is False
    assert any("PostgreSQL" in blocker for blocker in preview.blockers)
