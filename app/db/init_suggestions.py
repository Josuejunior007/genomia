
from sqlalchemy import select

from app.db.session import Base, SessionLocal, engine
from app.models.suggestion import Suggestion


INITIAL_SUGGESTIONS = [
    {
        "table_name": "appatendimentoregistro",
        "kind": "documentation",
        "description": (
            "Registro principal dos atendimentos, "
            "identificado por protocolo."
        ),
        "confidence": 0.91,
        "rationale": (
            "Inferência ilustrativa baseada no nome da tabela "
            "e na coluna protocolo."
        ),
    },
    {
        "table_name": "boraconversaratendimentos",
        "kind": "relationship",
        "description": (
            "Não criar FK automática entre responsavelmatricula "
            "e boraconversarusuarios.id."
        ),
        "confidence": 0.97,
        "rationale": (
            "A matrícula funcional não representa necessariamente "
            "o ID do usuário."
        ),
    },
    {
        "table_name": "atendimentosunificados",
        "kind": "naming",
        "description": (
            "Avaliar nomes descritivos e consistentes "
            "para os campos de matrícula."
        ),
        "confidence": 0.63,
        "rationale": (
            "Sugestão demonstrativa que exige validação humana."
        ),
    },
]


def initialize_suggestions():
    # Cria somente a tabela do modelo Suggestion, se necessário.
    Base.metadata.create_all(
        bind=engine,
        tables=[Suggestion.__table__],
    )

    with SessionLocal() as db:
        existing_id = db.scalar(
            select(Suggestion.id).limit(1)
        )

        if existing_id is not None:
            print(
                "A tabela já contém sugestões. "
                "Nenhum registro foi inserido."
            )
            return

        db.add_all(
            [
                Suggestion(
                    **data,
                    status="pending",
                )
                for data in INITIAL_SUGGESTIONS
            ]
        )

        db.commit()

        print(
            f"{len(INITIAL_SUGGESTIONS)} sugestões "
            "inseridas com sucesso."
        )


if __name__ == "__main__":
    initialize_suggestions()
