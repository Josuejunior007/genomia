from unittest.mock import MagicMock, patch

from scripts.check_read_only import CHECK_SQL, main


def test_check_query_covers_role_schema_and_table_write_privileges():
    sql = str(CHECK_SQL).lower()
    assert "rolsuper" in sql
    assert "has_schema_privilege" in sql
    assert "has_table_privilege" in sql
    assert "has_any_column_privilege" in sql


def test_validator_succeeds_for_read_only_role():
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.dialect.name = "postgresql"
    connection.execute.return_value.mappings.return_value.one.return_value = {
        "elevated_role": False,
        "schema_usage": True,
        "schema_create": False,
        "has_write_access": False,
    }
    connection.exec_driver_sql.return_value.scalar_one.return_value = "genomia_reader"

    with patch("scripts.check_read_only.create_engine", return_value=engine):
        assert main() == 0


def test_validator_fails_when_role_can_write():
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.dialect.name = "postgresql"
    connection.execute.return_value.mappings.return_value.one.return_value = {
        "elevated_role": False,
        "schema_usage": True,
        "schema_create": False,
        "has_write_access": True,
    }

    with patch("scripts.check_read_only.create_engine", return_value=engine):
        assert main() == 1
