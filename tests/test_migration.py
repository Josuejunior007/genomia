"""Testes unitários da migração de sugestões legadas."""

from __future__ import annotations

import sqlite3

from scripts.migrate_app_store import _read_sqlite, _row_to_suggestion


def test_row_normalization_maps_legacy_columns():
    item = _row_to_suggestion(
        {
            "table": "clientes",
            "kind": "documentation",
            "description": "Documentar clientes.",
            "confidence": 0.8,
            "status": "approved",
            "rationale": "Metadados.",
            "created_at": "2026-01-01T10:00:00",
        }
    )
    assert item["table_name"] == "clientes"
    assert item["status"] == "approved"
    assert item["created_at"].year == 2026


def test_invalid_status_is_normalized_to_pending():
    item = _row_to_suggestion({"table_name": "x", "status": "invalido"})
    assert item["status"] == "pending"


def test_read_sqlite_returns_rows(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE suggestions (id INTEGER PRIMARY KEY, \"table\" TEXT, kind TEXT, "
        "description TEXT, confidence REAL, status TEXT, rationale TEXT)"
    )
    connection.execute(
        "INSERT INTO suggestions (\"table\", kind, description, confidence, status, rationale) "
        "VALUES ('clientes', 'index', 'Criar índice.', 0.7, 'pending', 'Evidência.')"
    )
    connection.commit()
    connection.close()

    rows = _read_sqlite(path)
    assert len(rows) == 1
    assert rows[0]["table"] == "clientes"
