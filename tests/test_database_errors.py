import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, TimeoutError as SQLAlchemyTimeoutError

from app import main


client = TestClient(main.app)


@pytest.mark.parametrize(
    "database_error",
    [
        OperationalError("SELECT 1", {}, Exception("connection refused")),
        SQLAlchemyTimeoutError("QueuePool limit reached; connection timed out"),
    ],
    ids=["connection-error", "pool-timeout"],
)
def test_health_returns_standardized_503_for_database_errors(monkeypatch, database_error):
    def fail_to_connect():
        raise database_error

    monkeypatch.setattr(main.engine, "connect", fail_to_connect)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "API ativa, mas o banco de dados está indisponível. Tente novamente mais tarde.",
        "code": "database_unavailable",
    }
