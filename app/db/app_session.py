from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

_connect_args = {"check_same_thread": False} if settings.app_database_url.startswith("sqlite") else {}
app_engine = create_engine(
    settings.app_database_url,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
AppSessionLocal = sessionmaker(bind=app_engine, autoflush=False, autocommit=False)


def get_app_db():
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()
