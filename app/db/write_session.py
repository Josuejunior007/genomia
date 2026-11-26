"""Conexão opcional de escrita no banco analisado.

Fica separada da conexão read-only e só é criada quando ``WRITE_DATABASE_URL``
está configurada. A aplicação nunca usa essa engine para leitura de catálogo,
para a IA ou para o armazenamento de sugestões. Seu único uso é o endpoint de
aplicação de mudanças aprovadas.
"""

from __future__ import annotations

import threading

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import settings

_engine: Engine | None = None
_lock = threading.Lock()


def get_write_engine() -> Engine | None:
    """Retorna a engine de escrita (ou ``None`` se não configurada)."""
    global _engine
    if not settings.write_database_url:
        return None
    with _lock:
        if _engine is None:
            connect_args = (
                {"connect_timeout": 5}
                if settings.write_database_url.startswith("postgresql")
                else {}
            )
            _engine = create_engine(
                settings.write_database_url,
                pool_pre_ping=True,
                pool_recycle=1800,
                pool_size=2,
                max_overflow=2,
                connect_args=connect_args,
            )
        return _engine


def reset_write_engine() -> None:
    """Descarta a engine cacheada (usado em testes)."""
    global _engine
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
