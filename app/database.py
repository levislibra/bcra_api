import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

DEFAULT_DATABASE_URL = "postgresql://user_bcra:bcra1234@bcra_db:5432/bcra_deudores"


def _get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip()
    if len(database_url) >= 2 and database_url[0] == database_url[-1] and database_url[0] in {'"', "'"}:
        return database_url[1:-1]
    return database_url


DATABASE_URL = _get_database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
