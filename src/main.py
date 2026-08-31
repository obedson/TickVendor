#!/usr/bin/env python3
"""TickEven Application Factory and Entry Point."""

from src.config import settings
from src.database import engine, Base

def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")

if __name__ == "__main__":
    create_tables()