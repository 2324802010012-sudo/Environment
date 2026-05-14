import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional until requirements are installed
    load_dotenv = None


if load_dotenv:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root@localhost:3306/air_quality?charset=utf8mb4",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
