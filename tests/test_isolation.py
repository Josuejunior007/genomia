"""Testes do diagnóstico de isolamento do armazenamento interno."""

from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from app.db import app_session


def fake_engine(url: str, dialect: str = "postgresql"):
    return SimpleNamespace(
        dialect=SimpleNamespace(name=dialect),
        url=make_url(url),
    )


def test_sqlite_store_warns(monkeypatch):
    monkeypatch.setattr(
        app_session, "app_engine", fake_engine("sqlite:///./genomai_app.db", "sqlite")
    )
    analyzed = fake_engine("postgresql+psycopg://reader@host:5432/db")
    warnings = app_session.validate_store_isolation(analyzed)
    assert any("SQLite local" in warning for warning in warnings)


def test_same_schema_is_rejected(monkeypatch):
    monkeypatch.setattr(
        app_session,
        "app_engine",
        fake_engine("postgresql+psycopg://writer@host:5432/db"),
    )
    monkeypatch.setattr(app_session.settings, "app_db_schema", "public")
    monkeypatch.setattr(app_session.settings, "db_schema", "public")
    analyzed = fake_engine("postgresql+psycopg://reader@host:5432/db")
    with pytest.raises(RuntimeError, match="schema"):
        app_session.validate_store_isolation(analyzed)


def test_same_role_is_rejected(monkeypatch):
    monkeypatch.setattr(
        app_session,
        "app_engine",
        fake_engine("postgresql+psycopg://same_user@host:5432/db"),
    )
    monkeypatch.setattr(app_session.settings, "app_db_schema", "genomai_app")
    monkeypatch.setattr(app_session.settings, "db_schema", "public")
    analyzed = fake_engine("postgresql+psycopg://same_user@host:5432/db")
    with pytest.raises(RuntimeError, match="mesma role"):
        app_session.validate_store_isolation(analyzed)


def test_different_role_and_schema_is_allowed(monkeypatch):
    monkeypatch.setattr(
        app_session,
        "app_engine",
        fake_engine("postgresql+psycopg://writer@host:5432/db"),
    )
    monkeypatch.setattr(app_session.settings, "app_db_schema", "genomai_app")
    monkeypatch.setattr(app_session.settings, "db_schema", "public")
    analyzed = fake_engine("postgresql+psycopg://reader@host:5432/db")
    warnings = app_session.validate_store_isolation(analyzed)
    assert any("mesmo servidor" in warning for warning in warnings)
