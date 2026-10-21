import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session, sessionmaker

Base = declarative_base()

_env_file: Path | None = None
for parent in Path(__file__).resolve().parents:
    if (parent / "docker-compose.yml").is_file():
        candidate = parent / ".env"
        if candidate.is_file():
            _env_file = candidate
        break

if _env_file is None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            _env_file = candidate
            break

if _env_file is not None:
    load_dotenv(_env_file, override=False)
else:
    load_dotenv(override=False)


# class Base(DeclarativeBase):
#     pass


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:change-me@localhost:5433/sawakli",
)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
