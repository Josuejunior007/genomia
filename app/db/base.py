"""Base declarativa e utilitários de schema do armazenamento interno.

As tabelas do GenomAI vivem em um schema próprio (``APP_DB_SCHEMA``) quando o
banco interno é PostgreSQL. Isso mantém sugestões, revisões e auditorias
fisicamente separadas das tabelas que a IA pode analisar.
"""

from typing import Any

from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base do banco interno do GenomAI, separado dos dados inspecionados."""


def app_table_args(*args: Any) -> Any:
    """Monta ``__table_args__`` aplicando o schema interno quando necessário.

    Em SQLite não existe schema nomeado; nesse caso as tabelas ficam no arquivo
    local. Em PostgreSQL, todas as tabelas internas ficam em ``APP_DB_SCHEMA``.
    """
    options: dict[str, Any] = {}
    if settings.app_store_schema:
        options["schema"] = settings.app_store_schema
    if args:
        return (*args, options)
    return options
