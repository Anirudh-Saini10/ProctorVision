"""
Auth routes — proctor register / login / me.

Candidates do NOT have accounts; they join exams anonymously via the
join code. So this module only ever issues tokens for proctors.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from db import get_session
from models import Proctor
from security import (
    create_access_token,
    current_proctor,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── schemas ------------------------------------------------------------

class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    proctor: dict


class MeOut(BaseModel):
    id: int
    email: EmailStr
    name: str


# ── routes -------------------------------------------------------------

@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, session: Session = Depends(get_session)):
    existing = session.exec(
        select(Proctor).where(Proctor.email == body.email.lower())
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )
    proctor = Proctor(
        email=body.email.lower(),
        name=body.name.strip(),
        password_hash=hash_password(body.password),
    )
    session.add(proctor)
    session.commit()
    session.refresh(proctor)

    token = create_access_token(proctor.id)
    return TokenOut(
        access_token=token,
        proctor={"id": proctor.id, "email": proctor.email, "name": proctor.name},
    )


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, session: Session = Depends(get_session)):
    proctor = session.exec(
        select(Proctor).where(Proctor.email == body.email.lower())
    ).first()
    if not proctor or not verify_password(body.password, proctor.password_hash):
        # Generic message — don't leak whether the email exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    token = create_access_token(proctor.id)
    return TokenOut(
        access_token=token,
        proctor={"id": proctor.id, "email": proctor.email, "name": proctor.name},
    )


@router.get("/me", response_model=MeOut)
def me(proctor: Proctor = Depends(current_proctor)):
    return MeOut(id=proctor.id, email=proctor.email, name=proctor.name)
