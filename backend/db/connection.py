import os
from sqlalchemy import create_engine
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
