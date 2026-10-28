
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.db.session import get_db


client = TestClient(app)


def make_fake_db(total=0, pending=0, approved=0, rejected=0):
    fake_db = MagicMock()
    fake_db.scalar.side_effect = [
        total,
        pending,
        approved,
        rejected,
    ]
    return fake_db


def request_metrics(fake_db, fake_snapshot):
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        with patch(
            "app.api.v1.endpoints.dashboard.SchemaService"
        ) as mock_service:
            mock_service.return_value.snapshot.return_value = fake_snapshot
            return client.get("/api/v1/dashboard/metrics")
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_dashboard_metrics_returns_503_when_database_fails():
    with patch(
        "app.api.v1.endpoints.dashboard.SchemaService"
    ) as mock_service:
        mock_service.return_value.snapshot.side_effect = SQLAlchemyError(
            "Banco indisponível"
        )

        response = client.get("/api/v1/dashboard/metrics")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Métricas indisponíveis; verifique a conexão com o banco."
    )


def test_dashboard_metrics_returns_correct_counts():
    tables = [
        SimpleNamespace(
            name="app_clientes",
            columns=["id", "nome"],
            primary_key=["id"],
        ),
        SimpleNamespace(
            name="app_pedidos",
            columns=["id", "cliente_id"],
            primary_key=[],
        ),
        SimpleNamespace(
            name="relatorios",
            columns=["codigo"],
            primary_key=[],
        ),
    ]

    fake_snapshot = SimpleNamespace(tables=tables)
    fake_db = make_fake_db(
        total=3,
        pending=2,
        approved=1,
        rejected=0,
    )

    response = request_metrics(fake_db, fake_snapshot)

    assert response.status_code == 200

    data = response.json()
    assert data["tables_total"] == 3
    assert data["tables_with_basic_metadata"] == 3
    assert data["metadata_coverage_percent"] == 100.0
    assert data["tables_without_primary_key"] == 2
    assert data["total_suggestions"] == 3
    assert data["pending_suggestions"] == 2
    assert data["approved_suggestions"] == 1
    assert data["rejected_suggestions"] == 0
    assert data["reviewed_suggestions"] == 1
    assert data["review_rate_percent"] == 33.3


def test_dashboard_metrics_returns_zero_coverage_when_no_tables():
    fake_snapshot = SimpleNamespace(tables=[])
    fake_db = make_fake_db()

    response = request_metrics(fake_db, fake_snapshot)

    assert response.status_code == 200

    data = response.json()
    assert data["tables_total"] == 0
    assert data["tables_with_basic_metadata"] == 0
    assert data["metadata_coverage_percent"] == 0
    assert data["tables_without_primary_key"] == 0
    assert data["total_suggestions"] == 0
    assert data["pending_suggestions"] == 0
    assert data["approved_suggestions"] == 0
    assert data["rejected_suggestions"] == 0
    assert data["reviewed_suggestions"] == 0
    assert data["review_rate_percent"] == 0


def test_dashboard_excludes_tables_without_columns_from_coverage():
    tables = [
        SimpleNamespace(
            name="clientes",
            columns=["id"],
            primary_key=["id"],
        ),
        SimpleNamespace(
            name="vazia",
            columns=[],
            primary_key=[],
        ),
    ]

    fake_snapshot = SimpleNamespace(tables=tables)
    fake_db = make_fake_db()

    response = request_metrics(fake_db, fake_snapshot)

    assert response.status_code == 200

    data = response.json()
    assert data["tables_total"] == 2
    assert data["tables_with_basic_metadata"] == 1
    assert data["metadata_coverage_percent"] == 50.0
    assert data["tables_without_primary_key"] == 1
