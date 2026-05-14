"""
Attempt lifecycle (candidate-facing).

    POST /api/attempts                — start a new attempt for a code
    POST /api/attempts/{id}/submit    — submit answers + final summary, get score
    GET  /api/attempts/{id}/result    — fetch grading + integrity summary

The proctor-side view of an attempt lives in /api/exams/{id}/attempts.

Identity model
--------------
There is no candidate auth. To start an attempt you only need the
exam's join code and your name. The server returns an ``attempt_id``,
which the candidate's frontend keeps in memory and replays on submit.
This is fine for a portfolio / classroom setting; if this app ever
needed to resist motivated candidates we'd add a per-attempt token
issued at start that submit must replay. (Easy follow-up.)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session
from models import (
    Answer,
    Attempt,
    AttemptStatus,
    Exam,
    ExamStatus,
    Question,
    QuestionKind,
)

router = APIRouter(prefix="/api/attempts", tags=["attempts"])


# ── schemas ------------------------------------------------------------

class StartIn(BaseModel):
    code: str = Field(min_length=4, max_length=12)
    candidate_name: str = Field(min_length=1, max_length=120)


class StartOut(BaseModel):
    attempt_id: int
    exam_id: int
    title: str
    duration_min: int
    strictness: str


class AnswerIn(BaseModel):
    question_id: int
    selected_index: Optional[int] = None
    text: Optional[str] = None


class SubmitIn(BaseModel):
    answers: List[AnswerIn]
    proctor_session_id: Optional[str] = None


class SubmitOut(BaseModel):
    attempt_id: int
    status: AttemptStatus
    auto_score: int
    max_auto_score: int


class ResultOut(BaseModel):
    attempt_id: int
    status: AttemptStatus
    candidate_name: str
    started_at: datetime
    submitted_at: Optional[datetime]
    auto_score: Optional[int]
    max_auto_score: Optional[int]
    proctor_session_id: Optional[str]
    integrity_summary: Optional[dict]


# ── routes -------------------------------------------------------------

@router.post("", response_model=StartOut)
def start_attempt(body: StartIn, session: Session = Depends(get_session)):
    exam = session.exec(
        select(Exam).where(Exam.code == body.code.upper())
    ).first()
    if not exam:
        raise HTTPException(404, "No exam with that code.")
    if exam.status != ExamStatus.live:
        raise HTTPException(403, "This exam is not accepting attempts right now.")

    attempt = Attempt(
        exam_id=exam.id,
        candidate_name=body.candidate_name.strip(),
        status=AttemptStatus.in_progress,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)

    return StartOut(
        attempt_id=attempt.id,
        exam_id=exam.id,
        title=exam.title,
        duration_min=exam.duration_min,
        strictness=exam.strictness,
    )


@router.post("/{attempt_id}/submit", response_model=SubmitOut)
def submit_attempt(
    attempt_id: int,
    body: SubmitIn,
    session: Session = Depends(get_session),
):
    # Auto-grade MCQs against stored ``correct_index``. Short-answer
    # questions count toward ``max_auto_score`` as 0 (i.e. they are
    # not auto-graded; the proctor reads them off the report).
    attempt = session.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(404, "Attempt not found.")
    if attempt.status != AttemptStatus.in_progress:
        # Idempotent re-submit: just hand back the existing result.
        return SubmitOut(
            attempt_id=attempt.id,
            status=attempt.status,
            auto_score=attempt.auto_score or 0,
            max_auto_score=attempt.max_auto_score or 0,
        )

    questions = session.exec(
        select(Question).where(Question.exam_id == attempt.exam_id)
    ).all()
    by_id = {q.id: q for q in questions}

    # Wipe any prior partial answers (in case of re-submit during retry).
    for old in list(attempt.answers or []):
        session.delete(old)
    session.flush()

    auto_score = 0
    max_auto = 0
    for q in questions:
        if q.kind == QuestionKind.mcq:
            max_auto += q.points

    for a in body.answers:
        q = by_id.get(a.question_id)
        if not q:
            continue
        is_correct: Optional[bool] = None
        if q.kind == QuestionKind.mcq:
            is_correct = (
                a.selected_index is not None
                and a.selected_index == q.correct_index
            )
            if is_correct:
                auto_score += q.points
        session.add(Answer(
            attempt_id=attempt.id,
            question_id=q.id,
            selected_index=a.selected_index if q.kind == QuestionKind.mcq else None,
            text=a.text if q.kind == QuestionKind.short else None,
            is_correct=is_correct,
        ))

    attempt.submitted_at = datetime.utcnow()
    attempt.status = AttemptStatus.submitted
    attempt.auto_score = auto_score
    attempt.max_auto_score = max_auto
    if body.proctor_session_id:
        attempt.proctor_session_id = body.proctor_session_id
    session.add(attempt)
    session.commit()
    session.refresh(attempt)

    return SubmitOut(
        attempt_id=attempt.id,
        status=attempt.status,
        auto_score=auto_score,
        max_auto_score=max_auto,
    )


@router.get("/{attempt_id}/result", response_model=ResultOut)
def get_result(attempt_id: int, session: Session = Depends(get_session)):
    attempt = session.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(404, "Attempt not found.")
    return ResultOut(
        attempt_id=attempt.id,
        status=attempt.status,
        candidate_name=attempt.candidate_name,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        auto_score=attempt.auto_score,
        max_auto_score=attempt.max_auto_score,
        proctor_session_id=attempt.proctor_session_id,
        integrity_summary=attempt.integrity_summary,
    )
