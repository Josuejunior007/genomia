"""Configuração da conexão com o banco analisado (somente leitura).

Esta engine é usada apenas para introspecção e leitura de amostras. Nunca é
usada para gravar sugestões (isso é responsabilidade de ``app_session``) nem para
aplicar mudanças (``write_session``).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=3,
    max_overflow=5,
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """Dependency opcional para uma sessão do banco analisado.

    As rotas atuais usam a engine diretamente; esta dependency fica disponível
    para extensões que precisem de uma sessão ORM.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
