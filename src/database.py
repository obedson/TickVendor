"""TickEven Database — Engine, session factory, and declarative Base."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

database_url = os.environ.get("DATABASE_URL", "sqlite:///./tickeven.db")
engine = create_engine(database_url, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency: yield a DB session and ensure cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()