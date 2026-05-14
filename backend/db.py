"""
ProctorVision — Database
========================
Tiny SQLModel/SQLite layer. Designed to be zero-ops on Render: the
default database lives at ``data/proctorvision.db`` (which Render's
persistent disk mounts at ``/var/data``), and we ``create_all`` the
schema on app startup. There are no migrations because the schema is
small and we'd rather drop/rewrite during early iteration than maintain
Alembic for a portfolio project. Once this stops being a portfolio
project, swap in Alembic.

Environment variables:
    DATABASE_URL — full SQLAlchemy URL. Defaults to a local SQLite file.
                   On Render set this to ``sqlite:////var/data/proctorvision.db``
                   so the file lives on the persistent disk.
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

# Ensure the directory for the DB file exists (needed on Render where
# the persistent disk mount point may not exist until first use).
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL[len("sqlite:///"):].lstrip("/")
    # On Unix absolute paths need a leading slash; on Windows they don't.
    if os.name != "nt" and not db_path.startswith("/"):
        db_path = "/" + db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

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
