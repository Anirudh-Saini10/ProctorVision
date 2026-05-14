"""
ProctorVision — Data Models
===========================
SQLModel tables for the product layer (auth + exam authoring + attempts).

Schema overview:

    Proctor 1 ── n Exam 1 ── n Question
                    │
                    └── n Attempt 1 ── n Answer

Notes
-----
- ``Exam.code`` is the join code candidates type into the lobby. We
  generate a 6-char alphanumeric (no ambiguous chars) on creation and
  enforce a unique index so collisions raise instead of silently
  letting two exams share a code.
- ``Question.kind`` is either ``mcq`` or ``short`` (mixed quizzes are
  the chosen scope). MCQ stores ``options`` as a JSON list of strings
  and ``correct_index`` as an int; short-answer leaves both null.
- ``Attempt`` is the candidate's run-through. The CV/proctoring layer
  links to it via ``proctor_session_id`` (the UUID minted by the
  pipeline) so the integrity report and the quiz score live on the
  same row and are downloadable together.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Mapped
from sqlmodel import Column, Field, JSON, Relationship, SQLModel


# ── enums --------------------------------------------------------------

class QuestionKind(str, enum.Enum):
    mcq = "mcq"
    short = "short"


class ExamStatus(str, enum.Enum):
    draft = "draft"      # not yet published, code not usable
    live = "live"        # candidates can join
    closed = "closed"    # no new attempts accepted


class AttemptStatus(str, enum.Enum):
    in_progress = "in_progress"
    submitted = "submitted"
    abandoned = "abandoned"   # candidate disconnected without submit
    force_ended = "force_ended"   # proctor killed the session


# ── tables -------------------------------------------------------------

class Proctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    exams: Mapped[List["Exam"]] = Relationship(back_populates="proctor")


class Exam(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    proctor_id: int = Field(foreign_key="proctor.id", index=True)
    title: str
    description: str = ""
    code: str = Field(index=True, unique=True)
    strictness: str = "moderate"   # lenient | moderate | strict
    duration_min: int = 30
    status: ExamStatus = Field(default=ExamStatus.draft)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    proctor: Mapped[Optional["Proctor"]] = Relationship(back_populates="exams")
    questions: Mapped[List["Question"]] = Relationship(
        back_populates="exam",
        sa_relationship_kwargs={"order_by": "Question.idx", "cascade": "all, delete-orphan"},
    )
    attempts: Mapped[List["Attempt"]] = Relationship(back_populates="exam")


class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id", index=True)
    idx: int                              # 0..n display order
    kind: QuestionKind = Field(default=QuestionKind.mcq)
    prompt: str
    # MCQ-only: list of strings
    options: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    # MCQ-only: index into ``options``. Null for short-answer questions.
    correct_index: Optional[int] = None
    points: int = 1

    exam: Mapped[Optional["Exam"]] = Relationship(back_populates="questions")


class Attempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id", index=True)
    candidate_name: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    status: AttemptStatus = Field(default=AttemptStatus.in_progress)
    # Filled in once auto-grading runs (MCQ-only). Short answers contribute
    # 0 here and the proctor reads them off the report.
    auto_score: Optional[int] = None
    max_auto_score: Optional[int] = None
    # Link to the ProctorVision CV session UUID — set when the candidate
    # opens the WS and starts streaming frames. The integrity summary
    # (peak risk, violations, evidence frames) lives in the in-memory
    # ws_handler under this id; we also persist a snapshot of it here
    # at submission time for resilience.
    proctor_session_id: Optional[str] = Field(default=None, index=True)
    integrity_summary: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    exam: Mapped[Optional["Exam"]] = Relationship(back_populates="attempts")
    answers: Mapped[List["Answer"]] = Relationship(
        back_populates="attempt",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Answer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempt.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    # MCQ: candidate's chosen index. short: null.
    selected_index: Optional[int] = None
    # short: free text. MCQ: null.
    text: Optional[str] = None
    is_correct: Optional[bool] = None    # MCQ-only after grading

    attempt: Mapped[Optional["Attempt"]] = Relationship(back_populates="answers")
