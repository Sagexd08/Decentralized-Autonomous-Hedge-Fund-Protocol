import os
<<<<<<< HEAD
from sqlalchemy import create_engine, text
=======
from sqlalchemy import create_engine
>>>>>>> D!
from sqlalchemy.orm import sessionmaker
from core.settings import settings

DATABASE_URL = settings.database_url or os.getenv("DATABASE_URL", "sqlite:///./dacap.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
<<<<<<< HEAD


def fetch_all_dicts(query: str, params: dict | None = None) -> list[dict]:
    with engine.connect() as connection:
        result = connection.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]


def fetch_one_dict(query: str, params: dict | None = None) -> dict | None:
    with engine.connect() as connection:
        result = connection.execute(text(query), params or {})
        row = result.first()
        return dict(row._mapping) if row else None


def execute_statement(query: str, params: dict | None = None) -> None:
    with engine.begin() as connection:
        connection.execute(text(query), params or {})
=======
>>>>>>> D!
