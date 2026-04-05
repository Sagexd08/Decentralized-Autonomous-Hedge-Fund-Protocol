import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Resolve DATABASE_URL — import settings lazily to avoid circular imports at
# module load time when the DB is unreachable.
def _get_database_url() -> str:
    try:
        from core.settings import settings
        return settings.database_url or os.getenv("DATABASE_URL", "sqlite:///./iris.db")
    except Exception:
        return os.getenv("DATABASE_URL", "sqlite:///./iris.db")


DATABASE_URL = _get_database_url()

# Build engine with connection-pool settings that tolerate transient failures.
try:
    _engine_kwargs: dict = {"pool_pre_ping": True}
    if DATABASE_URL.startswith("sqlite"):
        _engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        _engine_kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_timeout": 10})

    engine = create_engine(DATABASE_URL, **_engine_kwargs)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Database engine created: %s", DATABASE_URL.split("@")[-1])
except Exception as exc:
    logger.warning("Database engine creation failed (%s) — DB calls will be no-ops.", exc)
    engine = None  # type: ignore[assignment]
    SessionLocal = None  # type: ignore[assignment]


def get_db():
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def fetch_all_dicts(query: str, params: dict | None = None) -> list[dict]:
    if engine is None:
        return []
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]


def fetch_one_dict(query: str, params: dict | None = None) -> dict | None:
    if engine is None:
        return None
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        row = result.first()
        return dict(row._mapping) if row else None


def execute_statement(query: str, params: dict | None = None) -> None:
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text(query), params or {})
