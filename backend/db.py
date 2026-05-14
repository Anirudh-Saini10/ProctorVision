"""
ProctorVision — Database
========================
Tiny SQLModel layer. Works with SQLite (local dev) or PostgreSQL
(Render production). Schema is created on app startup.

Environment variables:
    DATABASE_URL — full SQLAlchemy URL.
                   Local dev: sqlite:///./data/proctorvision.db
                   Render:    postgresql://user:pass@host/db
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine


def _default_sqlite_url() -> str:
    """Local-dev default: ./data/proctorvision.db, created if missing."""
    here = Path(__file__).resolve().parent
    data_dir = here / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data_dir / 'proctorvision.db').as_posix()}"


DATABASE_URL = os.environ.get("DATABASE_URL") or _default_sqlite_url()

# SQLite needs ``check_same_thread=False`` because FastAPI runs
# request handlers in a threadpool and we open one Session per request.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
)


def init_db() -> None:
    """Create all tables. Safe to call repeatedly — no-op when current."""
    # Importing here so the model module is registered with SQLModel
    # metadata before ``create_all`` runs.
    from models import Proctor, Exam, Question, Attempt, Answer  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a short-lived DB session."""
    with Session(engine) as session:
        yield session
