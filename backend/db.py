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
import sys
from pathlib import Path
from typing import Iterator

print("[DB] importing sqlmodel...", flush=True)
from sqlmodel import SQLModel, Session, create_engine
print("[DB] sqlmodel ok", flush=True)


def _default_sqlite_url() -> str:
    """Local-dev default: ./data/proctorvision.db, created if missing."""
    here = Path(__file__).resolve().parent
    data_dir = here / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data_dir / 'proctorvision.db').as_posix()}"


DATABASE_URL = os.environ.get("DATABASE_URL") or _default_sqlite_url()
print(f"[DB] DATABASE_URL = {DATABASE_URL!r}", flush=True)

# SQLite needs ``check_same_thread=False`` because FastAPI runs
# request handlers in a threadpool and we open one Session per request.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

print("[DB] creating engine...", flush=True)
try:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args=_connect_args,
    )
    print("[DB] engine created ok", flush=True)
except Exception as exc:
    print(f"[DB] ENGINE CREATION FAILED: {type(exc).__name__}: {exc}", flush=True)
    import traceback
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    sys.exit(1)


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
