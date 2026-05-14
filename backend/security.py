"""
ProctorVision — Security
========================
Password hashing (bcrypt) and JWT issuing/verification for proctor auth.

The signing secret is read from ``JWT_SECRET``. In dev it falls back to
a local sentinel so the app boots without setup; in production set it
to a long random string. Tokens are 12 hours by default — short enough
that a stolen token expires before the day is out, long enough that a
proctor doesn't get logged out mid-exam.
"""

from __future__ import annotations

import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from db import get_session
from models import Proctor


# ── config -------------------------------------------------------------

JWT_SECRET = os.environ.get("JWT_SECRET") or "dev-only-change-me-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", "12"))

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ``tokenUrl`` is purely for the OpenAPI docs button — actual login
# happens via JSON POST to /api/auth/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ── passwords ----------------------------------------------------------

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ── tokens -------------------------------------------------------------

def create_access_token(proctor_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(proctor_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=JWT_EXPIRES_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[int]:
    """Return the proctor_id encoded in the token, or None if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (JWTError, ValueError):
        return None


# ── FastAPI dependency -------------------------------------------------

def current_proctor(
    token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> Proctor:
    """Resolve the bearer token to a Proctor, or 401."""
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise cred_exc
    pid = decode_token(token)
    if pid is None:
        raise cred_exc
    proctor = session.get(Proctor, pid)
    if not proctor:
        raise cred_exc
    return proctor


# ── helpers ------------------------------------------------------------

# Avoid characters that look alike (0/O, 1/I/L) so codes copied off a
# screen are unambiguous over a video call.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_exam_code(length: int = 6) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
