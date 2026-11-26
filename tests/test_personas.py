"""Testes de personas e da matriz de capacidades."""

import pytest
from fastapi import HTTPException

from app.core.personas import (
    APPLY,
    READ,
    REVIEW,
    SUGGEST,
    Persona,
    has_capability,
    parse_persona,
    persona_catalog,
    require_capability,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, Persona.LEITOR),
        ("", Persona.LEITOR),
        ("leitor", Persona.LEITOR),
        ("viewer", Persona.LEITOR),
        ("analista", Persona.ANALISTA),
        ("analyst", Persona.ANALISTA),
        ("desenvolvedor", Persona.DESENVOLVEDOR),
        ("developer", Persona.DESENVOLVEDOR),
        ("admin", Persona.ADMINISTRADOR),
        ("  ADMINISTRADOR  ", Persona.ADMINISTRADOR),
    ],
)
def test_parse_persona_accepts_aliases(raw, expected):
    assert parse_persona(raw) is expected


def test_parse_persona_rejects_unknown_value():
    with pytest.raises(HTTPException) as exc:
        parse_persona("root")
    assert exc.value.status_code == 400


def test_capability_matrix():
    assert has_capability(Persona.LEITOR, READ)
    assert not has_capability(Persona.LEITOR, SUGGEST)
    assert has_capability(Persona.ANALISTA, SUGGEST)
    assert has_capability(Persona.ANALISTA, REVIEW)
    assert not has_capability(Persona.ANALISTA, APPLY)
    assert has_capability(Persona.DESENVOLVEDOR, APPLY)
    assert has_capability(Persona.ADMINISTRADOR, APPLY)


def test_catalog_has_all_personas_and_labels():
    items = persona_catalog()
    assert [item["id"] for item in items] == [persona.value for persona in Persona]
    assert all(item["label"] and item["capabilities"] for item in items)


def test_require_capability_blocks_analyst_from_apply():
    dependency = require_capability(APPLY)
    with pytest.raises(HTTPException) as exc:
        dependency(Persona.ANALISTA)
    assert exc.value.status_code == 403
