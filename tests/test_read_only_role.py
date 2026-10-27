from unittest.mock import MagicMock, patch

import pytest

from app.db.permissions import CHECK_SQL, validate_read_only
from scripts.check_read_only import main


def test_check_query_covers_role_membership_database_schema_and_table_privileges():
    sql = str(CHECK_SQL).lower()
    assert "rolsuper" in sql
    assert "pg_auth_members" in sql
    assert "has_database_privilege" in sql
    assert "has_schema_privilege" in sql
    assert "has_table_privilege" in sql
    assert "has_any_column_privilege" in sql


def configured_engine(result):
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.one.return_value = result
    return engine


def test_validator_succeeds_for_read_only_role():
    engine = configured_engine({
        "elevated_role": False,
        "has_memberships": False,
        "schema_usage": True,
        "schema_create": False,
        "database_create": False,
        "has_write_access": False,
    })
    validate_read_only(engine, "public")
    assert engine.connect.return_value.__enter__.return_value.execute.call_count == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"has_write_access": True},
        {"schema_create": True},
        {"database_create": True},
        {"elevated_role": True},
        {"has_memberships": True},
        {"schema_usage": False},
    ],
)
def test_validator_rejects_unsafe_permissions(overrides):
    result = {
        "elevated_role": False,
        "has_memberships": False,
        "schema_usage": True,
        "schema_create": False,
        "database_create": False,
        "has_write_access": False,
        **overrides,
    }
    with pytest.raises(RuntimeError, match="somente leitura"):
        validate_read_only(configured_engine(result), "public")


def test_validator_rejects_non_postgresql_engine():
    engine = MagicMock()
    engine.dialect.name = "sqlite"
    with pytest.raises(RuntimeError, match="requer PostgreSQL"):
        validate_read_only(engine, "public")


def test_cli_returns_failure_when_runtime_permissions_are_unsafe():
    engine = MagicMock()
    with patch("scripts.check_read_only.create_engine", return_value=engine), patch(
        "scripts.check_read_only.validate_read_only",
        side_effect=RuntimeError("Permissões do PostgreSQL não são somente leitura"),
    ):
        assert main() == 1
    engine.dispose.assert_called_once()
