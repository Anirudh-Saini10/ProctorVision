"""
ProctorVision — FastAPI Server
=================================
Main entry point for the ProctorVision backend.

Endpoints:
    - WS  /ws                       → student WebSocket (frame stream)
    - WS  /ws/proctor               → proctor WebSocket (live console)
    - GET /api/health               → Health check
    - GET /api/sessions             → Live + ended session list (proctor dashboard)
    - GET /api/report/{session_id}  → Download PDF report
    - /api/auth/*                   → proctor register / login / me
    - /api/exams/*                  → exam authoring + lookup-by-code
    - /api/attempts/*               → candidate attempt lifecycle

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import sys
import traceback
from pathlib import Path

print("[STARTUP] main.py: importing fastapi...", flush=True)
from fastapi import FastAPI, HTTPException, WebSocket
print("[STARTUP] main.py: fastapi ok", flush=True)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
print("[STARTUP] main.py: fastapi extras ok", flush=True)

print("[STARTUP] main.py: importing db...", flush=True)
from db import init_db
print("[STARTUP] main.py: db ok", flush=True)

print("[STARTUP] main.py: importing report_generator...", flush=True)
from report_generator import generate_report
print("[STARTUP] main.py: report_generator ok", flush=True)

print("[STARTUP] main.py: importing routes...", flush=True)
from routes.attempts import router as attempts_router
from routes.auth import router as auth_router
from routes.exams import router as exams_router
print("[STARTUP] main.py: routes ok", flush=True)

print("[STARTUP] main.py: importing websocket_handler...", flush=True)
from websocket_handler import WebSocketHandler
print("[STARTUP] main.py: websocket_handler ok", flush=True)

# Store session summaries for report generation. Held in-process for
# fast access during a session; the canonical record is also persisted
# onto the Attempt row at submit time (see websocket_handler).
session_store = {}  # {session_id: summary_dict}

# --- App setup ---
app = FastAPI(
    title="ProctorVision API",
    description="AI-powered exam integrity platform backend",
    version="1.0.0",
)

# --- CORS configuration ---
# Allow all origins — auth is JWT header-based (not cookies), so wildcard
# CORS is safe and removes deployment configuration friction.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket handler (shared instance, shares session_store with /api/report) ---
ws_handler = WebSocketHandler(session_store=session_store)

# --- Routers ---
app.include_router(auth_router)
app.include_router(exams_router)
app.include_router(attempts_router)


# --- Routes ---

@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring and keepalive pings."""
    return JSONResponse({
        "status": "healthy",
        "service": "ProctorVision Backend",
        "version": "1.0.0",
    })


@app.get("/api/report/{session_id}")
async def download_report(session_id: str):
    """Download a PDF integrity report for a completed session."""
    if session_id not in session_store:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    summary = session_store[session_id]
    pdf_bytes = generate_report(summary)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="proctorvision_report_{session_id[:8]}.pdf"',
        },
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time frame processing (candidate side)."""
    await ws_handler.handle_connection(websocket)


@app.websocket("/ws/proctor")
async def proctor_websocket(websocket: WebSocket):
    """WebSocket endpoint for proctor console."""
    await ws_handler.handle_proctor_connection(websocket)


@app.get("/api/sessions")
async def list_sessions():
    """List currently live + recently ended proctoring sessions."""
    return JSONResponse({"sessions": ws_handler.list_active_sessions()})


# --- Static frontend (single-origin deploy) ---
_static_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# Global exception handler — logs full traceback so Render logs show the root cause
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print("=" * 60)
    print("UNHANDLED EXCEPTION")
    print("=" * 60)
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    print("=" * 60)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )

if _static_dir.is_dir():
    # Serve actual static files (assets, images, etc.) directly
    for subpath in ["assets", "images", "fonts", "css", "js"]:
        p = _static_dir / subpath
        if p.is_dir():
            app.mount(f"/{subpath}", StaticFiles(directory=str(p)), name=f"static_{subpath}")

    # SPA catch-all: serve index.html for any non-API, non-WS route
    @app.get("/{catchall:path}")
    def serve_spa(catchall: str):
        # These prefixes are handled by API routes above (registered earlier)
        # but we guard them explicitly just in case.
        if catchall.startswith("api/") or catchall.startswith("ws"):
            raise HTTPException(status_code=404, detail="Not found")
        index_file = _static_dir / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file))
        raise HTTPException(status_code=404, detail="index.html not found")
else:
    print(f"WARNING: Static frontend directory not found at {_static_dir}")
    print("API routes will work, but the React UI will not be served.")


# --- Startup event ---

@app.on_event("startup")
async def startup_event():
    init_db()
    # Quick DB smoke-test — verifies tables exist and relationships resolve
    from db import engine
    from sqlmodel import Session, select
    from models import Exam
    try:
        with Session(engine) as session:
            session.exec(select(Exam)).first()
        print("  DB: OK (smoke test passed)")
    except Exception as exc:
        print("  DB: SMOKE TEST FAILED —", exc)
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    print()
    print("=" * 60)
    print("  ProctorVision Backend — Starting up")
    print("=" * 60)
    print()
    print("  WebSocket endpoint: ws://localhost:8000/ws")
    print("  Health check:       http://localhost:8000/api/health")
    print("  API docs:           http://localhost:8000/docs")
    print()
    print("  CORS: allow all origins (JWT header auth)")
    print()
    print("  Ready for connections.")
    print()
