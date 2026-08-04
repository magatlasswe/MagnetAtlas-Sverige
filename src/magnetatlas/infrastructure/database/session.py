"""Database engine and session setup."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from magnetatlas.infrastructure.database.base import Base


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    """Create tables and return a configured session factory."""
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    engine: Engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
