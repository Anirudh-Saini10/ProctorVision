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
print(f"[DB] DATABASE_URL = {DATABASE_URL!r}")
print(f"[DB] DATABASE_URL starts with sqlite:/// = {DATABASE_URL.startswith('sqlite:///')}")

# SQLite needs ``check_same_thread=False`` because FastAPI runs
# request handlers in a threadpool and we open one Session per request.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
)


def _ensure_db_dir() -> None:
    """Create the parent directory for the SQLite file if possible.

    On Render the persistent disk mounts at ``/var/data``; that path
    may not exist until the first deploy finishes, so we retry lazily
    inside ``init_db()`` rather than crashing at module import time.
    """
    print(f"[DB] _ensure_db_dir() running for URL: {DATABASE_URL!r}")
    if not DATABASE_URL.startswith("sqlite:///"):
        print("[DB] URL does not start with sqlite:/// — skipping directory creation")
        return
    db_path = DATABASE_URL[len("sqlite:///"):].lstrip("/")
    print(f"[DB] parsed db_path = {db_path!r}")
    # On Unix absolute paths need a leading slash; on Windows they don't.
    if os.name != "nt" and not db_path.startswith("/"):
        db_path = "/" + db_path
    print(f"[DB] final db_path = {db_path!r}")
    dir_path = Path(db_path).parent
    print(f"[DB] dir_path = {dir_path!r}")
    print(f"[DB] dir exists = {dir_path.exists()}, dir is dir = {dir_path.is_dir() if dir_path.exists() else 'N/A'}")
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"[DB] mkdir succeeded for {dir_path}")
        # Test write permission by creating a temp file
        test_file = dir_path / ".db_write_test"
        try:
            test_file.write_text("ok")
            test_file.unlink()
            print(f"[DB] write test passed for {dir_path}")
        except Exception as exc:
            print(f"[DB] WRITE TEST FAILED for {dir_path}: {exc}")
    except PermissionError as exc:
        print(f"[DB] WARNING: Cannot create DB directory {dir_path}: {exc}")
        print("         If using Render, ensure the persistent disk is mounted.")
        # Don't raise — let the caller decide whether to continue.


def init_db() -> None:
    """Create all tables. Safe to call repeatedly — no-op when current."""
    _ensure_db_dir()

    # Importing here so the model module is registered with SQLModel
    # metadata before ``create_all`` runs.
    from models import Proctor, Exam, Question, Attempt, Answer  # noqa: F401

    print("[DB] Calling SQLModel.metadata.create_all(engine)...")
    try:
        SQLModel.metadata.create_all(engine)
        print("[DB] create_all succeeded")
    except Exception as exc:
        print(f"[DB] create_all FAILED: {type(exc).__name__}: {exc}")
        raise


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a short-lived DB session."""
    with Session(engine) as session:
        yield session
