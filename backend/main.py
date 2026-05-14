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

import os

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from db import init_db
from report_generator import generate_report
from routes.attempts import router as attempts_router
from routes.auth import router as auth_router
from routes.exams import router as exams_router
from websocket_handler import WebSocketHandler

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
# Dev defaults + any extra origins from FRONTEND_ORIGINS env var
# (comma-separated). On Render, set FRONTEND_ORIGINS to your static
# site URL so the browser can call the API.
DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
_extra = [o.strip() for o in os.environ.get("FRONTEND_ORIGINS", "").split(",") if o.strip()]
ALLOWED_ORIGINS = DEFAULT_ORIGINS + _extra

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
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


# --- Startup event ---

@app.on_event("startup")
async def startup_event():
    init_db()
    print()
    print("=" * 60)
    print("  ProctorVision Backend — Starting up")
    print("=" * 60)
    print()
    print("  WebSocket endpoint: ws://localhost:8000/ws")
    print("  Health check:       http://localhost:8000/api/health")
    print("  API docs:           http://localhost:8000/docs")
    print()
    print("  CORS allowed origins:")
    for origin in ALLOWED_ORIGINS:
        print(f"    - {origin}")
    print()
    print("  Ready for connections.")
    print()
