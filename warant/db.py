"""Database engine and session management."""

from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


def _build_engine() -> Engine:
    url = os.environ.get(
        "WARANT_DATABASE_URL", "sqlite:///warant.db?check_same_thread=false"
    )
    kwargs: dict = {"echo": False}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine: Engine = _build_engine()


def init_db() -> None:
    """Create all tables. Import warant.models first so metadata is filled."""
    import warant.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


@contextmanager
def game_session():
    """Session for game logic outside request handling."""
    with Session(engine) as session:
        yield session
