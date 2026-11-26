"""Testes da camada de privacidade: allowlist, redação e auditoria do payload."""

import json

import pytest

from app.privacy.metadata import (
    assert_safe_payload,
    build_safe_schema_context,
    classify_sensitive,
    sanitize_deterministic_report,
    sanitize_identifier,
)
from app.schemas.schema import (
    AnalysisReport,
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    Recommendation,
    SchemaSnapshot,
    TableInfo,
)


def _snapshot() -> SchemaSnapshot:
    return SchemaSnapshot(
        database="postgres",
        schema="public",
        tables=[
            TableInfo(
                name="clientes",
                schema="public",
                columns=[
                    ColumnInfo(
                        name="cpf",
                        type="VARCHAR(11)",
                        nullable=False,
                        default="'123.456.789-00'",
                        is_primary_key=False,
                    ),
                    ColumnInfo(
                        name="email_contato",
                        type="VARCHAR(150)",
                        nullable=True,
                        is_primary_key=False,
                    ),
                    ColumnInfo(
                        name="id",
                        type="INTEGER",
                        nullable=False,
                        is_primary_key=True,
                    ),
                ],
                primary_key=["id"],
                foreign_keys=[
                    ForeignKeyInfo(
                        constrained_columns=["id"],
                        referred_table="suggestions",
                        referred_schema="public",
                        referred_columns=["id"],
                    )
                ],
                indexes=[
                    IndexInfo(
                        name="ix_clientes_id",
                        column_names=["id"],
                        unique=False,
                    )
                ],
            ),
            TableInfo(
                name="suggestions",
                schema="public",
                columns=[ColumnInfo(name="id", type="INTEGER", nullable=False)],
                primary_key=["id"],
                foreign_keys=[],
                indexes=[],
            ),
        ],
    )


def test_sensitive_classification_covers_common_pii():
    assert classify_sensitive("cpf").value == "identificacao"
    assert classify_sensitive("email_contato").value == "contato"
    assert classify_sensitive("senha_hash").value == "autenticacao"
    assert classify_sensitive("prontuario_medico").value == "saude"
    assert classify_sensitive("cartao_credito").value == "financeiro"
    assert classify_sensitive("matricula").value == "profissional"
    assert classify_sensitive("quantidade") is None


def test_payload_contains_only_safe_metadata_and_no_defaults():
    safe = build_safe_schema_context(_snapshot())
    serialized = json.dumps(safe.payload.model_dump(mode="json"))

    assert "123.456.789-00" not in serialized
    assert "default" not in serialized.casefold()
    assert "suggestions" not in [table.name for table in safe.payload.tables]
    assert safe.report.tables_excluded >= 0
    assert safe.report.sensitive_columns == 2
    # FK para a tabela interna é removida do payload.
    assert all(not table.foreign_keys for table in safe.payload.tables)


def test_mask_sensitive_identifiers_pseudonymizes_columns():
    safe = build_safe_schema_context(_snapshot(), mask_sensitive=True)
    clientes = next(table for table in safe.payload.tables if table.name == "clientes")
    names = {column.name for column in clientes.columns}

    assert "cpf" not in names
    assert any(name.startswith("coluna_sensivel_") for name in names)
    assert safe.report.masked_sensitive_identifiers is True


def test_identifier_redaction_removes_emails_and_long_digits():
    text, count = sanitize_identifier("cpf_12345678900_contato@example.com")
    assert "12345678900" not in text
    assert "example.com" not in text
    assert count >= 1

    text_with_uuid, count_uuid = sanitize_identifier(
        "id_123e4567-e89b-12d3-a456-426614174000"
    )
    assert "123e4567" not in text_with_uuid
    assert count_uuid >= 1


def test_assert_safe_payload_rejects_rows_and_defaults():
    with pytest.raises(ValueError, match="campo proibido"):
        assert_safe_payload({"tables": [{"name": "x", "rows": [{"cpf": "123"}]}]})
    with pytest.raises(ValueError, match="campo proibido"):
        assert_safe_payload({"columns": [{"name": "x", "default": "'abc'"}]})


def test_assert_safe_payload_accepts_generated_payload():
    safe = build_safe_schema_context(_snapshot())
    assert_safe_payload(safe.payload)


def test_deterministic_report_is_sanitized():
    report = AnalysisReport(
        summary="2 tabelas; telefone 11999998888",
        tables_analyzed=2,
        recommendations=[
            Recommendation(
                severity="low",
                table="clientes",
                category="naming",
                message="Contato 11999998888",
                evidence="email a@b.com",
            )
        ],
    )
    safe = sanitize_deterministic_report(report)
    serialized = json.dumps(safe, ensure_ascii=False)
    assert "11999998888" not in serialized
    assert "a@b.com" not in serialized


def test_referred_columns_are_sanitized():
    table = TableInfo(
        name="pedidos",
        schema="public",
        columns=[ColumnInfo(name="cliente_id", type="INTEGER", nullable=False)],
        primary_key=[],
        foreign_keys=[
            ForeignKeyInfo(
                constrained_columns=["cliente_id"],
                referred_table="clientes_12345678900",
                referred_schema="public",
                referred_columns=["cpf_12345678900"],
            )
        ],
        indexes=[],
    )
    safe = build_safe_schema_context(
        SchemaSnapshot(database="postgres", schema="public", tables=[table])
    )
    serialized = json.dumps(safe.payload.model_dump(mode="json"))
    assert "12345678900" not in serialized
