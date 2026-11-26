"""Testes do fluxo de sugestões: criação, edição versionada e revisão parcial."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.endpoints import suggestions as endpoints
from app.core.personas import Persona
from app.db.base import Base
from app.schemas.schema import ReviewRequest, SuggestionCreate, SuggestionUpdate


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def fake_target(monkeypatch):
    monkeypatch.setattr(
        endpoints, "_resolve_target", lambda table, column: (table, column)
    )


def create(db: Session):
    return endpoints.create_suggestion(
        SuggestionCreate(
            table="clientes",
            kind="index",
            column_name="codigo",
            description="Criar índice para código.",
            confidence=0.8,
            rationale="A coluna não é a primeira de um índice.",
            suggested_sql="CREATE INDEX idx_x ON clientes (codigo);",
        ),
        db=db,
        persona=Persona.ANALISTA,
    )


def test_create_persists_pending_and_first_revision(db):
    item = create(db)

    assert item.id > 0
    assert item.status == "pending"
    assert item.version == 1
    assert item.revision_count == 1
    assert item.edited_by == "analista"


def test_edit_increments_version_and_reopens(db):
    item = create(db)

    updated = endpoints.update_suggestion(
        item.id,
        SuggestionUpdate(
            description="Criar índice para consultas por código.",
            comment="Ajuste solicitado pela mentora.",
        ),
        db=db,
        persona=Persona.ANALISTA,
    )

    assert updated.version == 2
    assert updated.status == "pending"
    assert updated.previous_status == "pending"
    assert updated.revision_count == 2

    revisions = endpoints.list_revisions(item.id, db=db, _persona=Persona.LEITOR)
    assert [revision.version for revision in revisions] == [1, 2]
    assert revisions[-1].comment == "Ajuste solicitado pela mentora."


def test_partial_approval_then_edit_returns_to_pending(db):
    item = create(db)

    review = endpoints.review_suggestion(
        item.id,
        ReviewRequest(decision="partially_approved", comment="Aprovar só o índice."),
        db=db,
        persona=Persona.ANALISTA,
    )
    assert review.status == "partially_approved"
    assert review.reviewed_by == "analista"

    updated = endpoints.update_suggestion(
        item.id,
        SuggestionUpdate(
            description="Índice apenas para o código.",
            comment="Ajustar escopo após aprovação parcial.",
        ),
        db=db,
        persona=Persona.ANALISTA,
    )
    assert updated.status == "pending"
    assert updated.previous_status == "partially_approved"
    assert updated.version == 2


def test_review_rejects_noop_and_applied(db):
    item = create(db)
    endpoints.review_suggestion(
        item.id,
        ReviewRequest(decision="approved"),
        db=db,
        persona=Persona.ANALISTA,
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        endpoints.review_suggestion(
            item.id,
            ReviewRequest(decision="approved"),
            db=db,
            persona=Persona.ANALISTA,
        )
    assert exc.value.status_code == 409


def test_edit_approved_without_reopen_is_rejected(db):
    from fastapi import HTTPException

    item = create(db)
    endpoints.review_suggestion(
        item.id,
        ReviewRequest(decision="approved"),
        db=db,
        persona=Persona.ANALISTA,
    )
    with pytest.raises(HTTPException) as exc:
        endpoints.update_suggestion(
            item.id,
            SuggestionUpdate(description="Alteração silenciosa.", reopen=False),
            db=db,
            persona=Persona.ANALISTA,
        )
    assert exc.value.status_code == 409


def test_viewer_cannot_be_used_for_suggest_capability_at_route_level(db):
    """A checagem de capacidade é feita pela dependency; aqui validamos a matriz."""

    from app.core.personas import SUGGEST, has_capability

    assert not has_capability(Persona.LEITOR, SUGGEST)
    assert has_capability(Persona.ANALISTA, SUGGEST)
