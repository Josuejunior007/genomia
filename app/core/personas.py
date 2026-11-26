"""Personas e capacidades do GenomAI.

O MVP não implementa autenticação completa. Para demonstrar a governança por
personas, a persona é declarada no cabeçalho ``X-GenomAI-Persona`` e validada
no backend. Em produção, substitua a dependency ``get_persona`` por uma
verificação de identidade (OIDC/JWT) mantendo a mesma matriz de capacidades.

Matriz:

==============  =========================================================
Persona         Pode
==============  =========================================================
``leitor``      Consultar catálogo, análise, sugestões e histórico.
``analista``    Criar, editar e revisar sugestões (inclusive parcialmente).
``desenvolvedor`` Tudo do analista + aplicar mudanças aprovadas no banco.
``administrador`` Tudo, incluindo auditoria e configuração.
==============  =========================================================
"""

from __future__ import annotations

from enum import Enum

from fastapi import Depends, Header, HTTPException

from app.core.config import settings


class Persona(str, Enum):
    """Perfis de acesso reconhecidos pela aplicação."""

    LEITOR = "leitor"
    ANALISTA = "analista"
    DESENVOLVEDOR = "desenvolvedor"
    ADMINISTRADOR = "administrador"


PERSONA_HEADER = "X-GenomAI-Persona"

# Capacidades atômicas usadas pelas rotas.
READ = "read"
SUGGEST = "suggest"
REVIEW = "review"
APPLY = "apply"
AUDIT = "audit"

CAPABILITIES: dict[Persona, frozenset[str]] = {
    Persona.LEITOR: frozenset({READ}),
    Persona.ANALISTA: frozenset({READ, SUGGEST, REVIEW}),
    Persona.DESENVOLVEDOR: frozenset({READ, SUGGEST, REVIEW, APPLY, AUDIT}),
    Persona.ADMINISTRADOR: frozenset({READ, SUGGEST, REVIEW, APPLY, AUDIT}),
}

PERSONA_LABELS: dict[Persona, str] = {
    Persona.LEITOR: "Leitor",
    Persona.ANALISTA: "Analista de dados",
    Persona.DESENVOLVEDOR: "Desenvolvedor",
    Persona.ADMINISTRADOR: "Administrador",
}

PERSONA_DESCRIPTIONS: dict[Persona, str] = {
    Persona.LEITOR: "Consulta catálogo, análise e sugestões, sem alterar nada.",
    Persona.ANALISTA: "Cria, edita e revisa sugestões; não executa mudanças no banco.",
    Persona.DESENVOLVEDOR: "Revisa e aplica mudanças aprovadas, com SQL validado pelo servidor.",
    Persona.ADMINISTRADOR: "Acesso completo, incluindo auditoria de aplicações.",
}

_ALIASES: dict[str, Persona] = {
    "leitor": Persona.LEITOR,
    "viewer": Persona.LEITOR,
    "read": Persona.LEITOR,
    "analista": Persona.ANALISTA,
    "analyst": Persona.ANALISTA,
    "data_analyst": Persona.ANALISTA,
    "desenvolvedor": Persona.DESENVOLVEDOR,
    "developer": Persona.DESENVOLVEDOR,
    "dev": Persona.DESENVOLVEDOR,
    "administrador": Persona.ADMINISTRADOR,
    "admin": Persona.ADMINISTRADOR,
    "owner": Persona.ADMINISTRADOR,
}


def parse_persona(value: str | None) -> Persona:
    """Converte o valor do cabeçalho em persona, aplicando aliases."""
    raw = (value or settings.default_persona or "leitor").strip().casefold()
    persona = _ALIASES.get(raw)
    if persona is None:
        allowed = ", ".join(item.value for item in Persona)
        raise HTTPException(
            status_code=400,
            detail=f"Persona inválida: {value!r}. Valores aceitos: {allowed}.",
        )
    return persona


def get_persona(
    x_genomai_persona: str | None = Header(default=None, alias=PERSONA_HEADER),
) -> Persona:
    """Dependency que resolve a persona da requisição."""
    return parse_persona(x_genomai_persona)


def has_capability(persona: Persona, capability: str) -> bool:
    """Informa se a persona possui a capacidade solicitada."""
    return capability in CAPABILITIES[persona]


def require_capability(capability: str):
    """Cria uma dependency que exige uma capacidade da persona."""

    def dependency(persona: Persona = Depends(get_persona)) -> Persona:
        if not has_capability(persona, capability):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"A persona {persona.value!r} não tem permissão para esta ação "
                    f"(capacidade necessária: {capability})."
                ),
            )
        return persona

    return dependency


def persona_catalog() -> list[dict[str, object]]:
    """Retorna a matriz de personas para consumo do frontend/documentação."""
    return [
        {
            "id": persona.value,
            "label": PERSONA_LABELS[persona],
            "description": PERSONA_DESCRIPTIONS[persona],
            "capabilities": sorted(CAPABILITIES[persona]),
        }
        for persona in Persona
    ]
