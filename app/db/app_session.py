from pathlib import Path

from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

app_database_url = make_url(settings.app_database_url)
if app_database_url.drivername.startswith("sqlite") and app_database_url.database not in (None, ":memory:"):
    database_path = Path(app_database_url.database)
    if not database_path.is_absolute():
        # Keep the local review database beside the project, regardless of PyCharm's working directory.
        database_path = (Path(__file__).resolve().parents[2] / database_path).resolve()
        app_database_url = app_database_url.set(database=str(database_path))

_connect_args = {"check_same_thread": False} if app_database_url.drivername.startswith("sqlite") else {}
app_engine = create_engine(
    app_database_url,
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
