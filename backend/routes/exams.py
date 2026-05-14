"""
Exam authoring routes (proctor-side) + public lookup-by-code route.

Proctor endpoints (require auth):
    POST   /api/exams              — create a new exam (with questions)
    GET    /api/exams              — list my exams
    GET    /api/exams/{id}         — fetch one of my exams (with questions)
    PATCH  /api/exams/{id}         — update title / strictness / status / etc.
    PUT    /api/exams/{id}/questions — replace the full question set
    DELETE /api/exams/{id}         — delete (only if no attempts)
    GET    /api/exams/{id}/attempts — list attempts for one of my exams

Public endpoints (no auth):
    GET    /api/exams/by-code/{code} — candidate-facing lookup; returns
           a sanitised payload (NO correct answers) so the frontend can
           render the quiz.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session
from models import (
    Attempt,
    AttemptStatus,
    Exam,
    ExamStatus,
    Proctor,
    Question,
    QuestionKind,
)
from security import current_proctor, generate_exam_code

router = APIRouter(prefix="/api/exams", tags=["exams"])


# ── schemas ------------------------------------------------------------

class QuestionIn(BaseModel):
    kind: QuestionKind = QuestionKind.mcq
    prompt: str = Field(min_length=1)
    options: Optional[List[str]] = None
    correct_index: Optional[int] = None
    points: int = 1


class QuestionOutProctor(QuestionIn):
    id: int
    idx: int


class QuestionOutPublic(BaseModel):
    """Candidate-facing question — correct_index is intentionally omitted."""
    id: int
    idx: int
    kind: QuestionKind
    prompt: str
    options: Optional[List[str]] = None
    points: int


class ExamCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    strictness: str = "moderate"
    duration_min: int = Field(default=30, ge=1, le=240)
    questions: List[QuestionIn] = Field(default_factory=list)


class ExamUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    strictness: Optional[str] = None
    duration_min: Optional[int] = None
    status: Optional[ExamStatus] = None


class ExamOutProctor(BaseModel):
    id: int
    title: str
    description: str
    code: str
    strictness: str
    duration_min: int
    status: ExamStatus
    question_count: int
    attempt_count: int
    questions: Optional[List[QuestionOutProctor]] = None


class ExamOutPublic(BaseModel):
    """Used by candidates after entering the join code."""
    id: int
    title: str
    description: str
    strictness: str
    duration_min: int
    questions: List[QuestionOutPublic]


# ── helpers ------------------------------------------------------------

def _validate_questions(questions: List[QuestionIn]) -> None:
    if len(questions) == 0:
        raise HTTPException(400, "An exam needs at least one question.")
    if len(questions) > 50:
        raise HTTPException(400, "Maximum 50 questions per exam.")
    for i, q in enumerate(questions):
        if q.kind == QuestionKind.mcq:
            if not q.options or len(q.options) < 2:
                raise HTTPException(400, f"Question {i + 1}: MCQ needs at least 2 options.")
            if q.correct_index is None or not (0 <= q.correct_index < len(q.options)):
                raise HTTPException(400, f"Question {i + 1}: correct_index out of range.")
        else:  # short
            if q.options or q.correct_index is not None:
                # Cleanly drop these on save — but warn loudly.
                raise HTTPException(
                    400,
                    f"Question {i + 1}: short-answer must not have options/correct_index.",
                )


def _exam_to_proctor_out(exam: Exam, include_questions: bool = False) -> ExamOutProctor:
    qcount = len(exam.questions) if exam.questions is not None else 0
    acount = len(exam.attempts) if exam.attempts is not None else 0
    return ExamOutProctor(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        code=exam.code,
        strictness=exam.strictness,
        duration_min=exam.duration_min,
        status=exam.status,
        question_count=qcount,
        attempt_count=acount,
        questions=[
            QuestionOutProctor(
                id=q.id,
                idx=q.idx,
                kind=q.kind,
                prompt=q.prompt,
                options=q.options,
                correct_index=q.correct_index,
                points=q.points,
            )
            for q in (exam.questions or [])
        ] if include_questions else None,
    )


def _unique_code(session: Session) -> str:
    # Vanishingly rare collision (~1 in 30^6) but loop just in case.
    for _ in range(20):
        code = generate_exam_code()
        if not session.exec(select(Exam).where(Exam.code == code)).first():
            return code
    raise HTTPException(500, "Could not allocate a unique exam code; try again.")


# ── proctor endpoints --------------------------------------------------

@router.post("", response_model=ExamOutProctor)
def create_exam(
    body: ExamCreateIn,
    session: Session = Depends(get_session),
    proctor: Proctor = Depends(current_proctor),
):
    _validate_questions(body.questions)
    exam = Exam(
        proctor_id=proctor.id,
        title=body.title.strip(),
        description=body.description.strip(),
        strictness=body.strictness,
        duration_min=body.duration_min,
        code=_unique_code(session),
        status=ExamStatus.live,    # publish immediately for portfolio simplicity
    )
    session.add(exam)
    session.flush()  # need exam.id for FK
    for i, q in enumerate(body.questions):
        session.add(Question(
            exam_id=exam.id,
            idx=i,
            kind=q.kind,
            prompt=q.prompt.strip(),
            options=q.options if q.kind == QuestionKind.mcq else None,
            correct_index=q.correct_index if q.kind == QuestionKind.mcq else None,
            points=q.points,
        ))
    session.commit()
    session.refresh(exam)
    return _exam_to_proctor_out(exam, include_questions=True)


@router.get("", response_model=List[ExamOutProctor])
def list_my_exams(
    session: Session = Depends(get_session),
    proctor: Proctor = Depends(current_proctor),
):
    rows = session.exec(
        select(Exam).where(Exam.proctor_id == proctor.id).order_by(Exam.created_at.desc())
    ).all()
    return [_exam_to_proctor_out(e) for e in rows]


@router.get("/{exam_id}", response_model=ExamOutProctor)
def get_my_exam(
    exam_id: int,
    session: Session = Depends(get_session),
    proctor: Proctor = Depends(current_proctor),
):
    exam = session.get(Exam, exam_id)
    if not exam or exam.proctor_id != proctor.id:
        raise HTTPException(404, "Exam not found.")
    return _exam_to_proctor_out(exam, include_questions=True)


@router.patch("/{exam_id}", response_model=ExamOutProctor)
def update_exam(
    exam_id: int,
    body: ExamUpdateIn,
    session: Session = Depends(get_session),
    proctor: Proctor = Depends(current_proctor),
):
    exam = session.get(Exam, exam_id)
    if not exam or exam.proctor_id != proctor.id:
        raise HTTPException(404, "Exam not found.")
    data = body.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(exam, k, v)
    session.add(exam)
    session.commit()
    session.refresh(exam)
    return _exam_to_proctor_out(exam, include_questions=True)


@router.put("/{exam_id}/questions", response_model=ExamOutProctor)
def replace_questions(
    exam_id: int,
    body: List[QuestionIn],
    session: Session = Depends(get_session),
    proctor: Proctor = Depends(current_proctor),
):
    exam = session.get(Exam, exam_id)
    if not exam or exam.proctor_id != proctor.id:
        raise HTTPException(404, "Exam not found.")
    _validate_questions(body)
    # Wipe + re-insert. Cheap for 10–50 rows; avoids reconciling diffs.
    for q in list(exam.questions or []):
        session.delete(q)
    session.flush()
    for i, q in enumerate(body):
        session.add(Question(
            exam_id=exam.id,
            idx=i,
            kind=q.kind,
            prompt=q.prompt.strip(),
            options=q.options if q.kind == QuestionKind.mcq else None,
            correct_index=q.correct_index if q.kind == QuestionKind.mcq else None,
            points=q.points,
        ))
    session.commit()
    session.refresh(exam)
    return _exam_to_proctor_out(exam, include_questions=True)


@router.delete("/{exam_id}", status_code=204)
def delete_exam(
    exam_id: int,
    session: Session = Depends(get_session),
    proctor: Proctor = Depends(current_proctor),
):
    exam = session.get(Exam, exam_id)
    if not exam or exam.proctor_id != proctor.id:
        raise HTTPException(404, "Exam not found.")
    if exam.attempts:
        raise HTTPException(
            409,
            "Cannot delete an exam with attempts. Close it instead.",
        )
    session.delete(exam)
    session.commit()


@router.get("/{exam_id}/attempts")
def list_attempts(
    exam_id: int,
    session: Session = Depends(get_session),
    proctor: Proctor = Depends(current_proctor),
):
    exam = session.get(Exam, exam_id)
    if not exam or exam.proctor_id != proctor.id:
        raise HTTPException(404, "Exam not found.")
    rows = session.exec(
        select(Attempt).where(Attempt.exam_id == exam_id).order_by(Attempt.started_at.desc())
    ).all()
    return [
        {
            "id": a.id,
            "candidate_name": a.candidate_name,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "status": a.status,
            "auto_score": a.auto_score,
            "max_auto_score": a.max_auto_score,
            "proctor_session_id": a.proctor_session_id,
            "peak_risk": (a.integrity_summary or {}).get("peak_risk"),
            "integrity_score": (a.integrity_summary or {}).get("integrity_score"),
        }
        for a in rows
    ]


# ── public (candidate-facing) -----------------------------------------

@router.get("/by-code/{code}", response_model=ExamOutPublic)
def fetch_by_code(code: str, session: Session = Depends(get_session)):
    exam = session.exec(
        select(Exam).where(Exam.code == code.upper())
    ).first()
    if not exam:
        raise HTTPException(404, "No exam with that code.")
    if exam.status != ExamStatus.live:
        raise HTTPException(403, "This exam is not currently accepting attempts.")
    return ExamOutPublic(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        strictness=exam.strictness,
        duration_min=exam.duration_min,
        questions=[
            QuestionOutPublic(
                id=q.id,
                idx=q.idx,
                kind=q.kind,
                prompt=q.prompt,
                options=q.options,
                points=q.points,
            )
            for q in exam.questions
        ],
    )
