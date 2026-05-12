"""
ProctorVision — FastAPI Server
=================================
Main entry point for the ProctorVision backend.

Endpoints:
    - WS  /ws                     → WebSocket for real-time frame processing
    - GET /api/health              → Health check
    - GET /api/report/{session_id} → Download PDF report (Phase 9)

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from websocket_handler import WebSocketHandler
from report_generator import generate_report

# Store session summaries for report generation
session_store = {}  # {session_id: summary_dict}

# --- App setup ---
app = FastAPI(
    title="ProctorVision API",
    description="AI-powered exam integrity platform backend",
    version="1.0.0",
)

# --- CORS configuration ---
# Allow the React dev server and future production domains
ALLOWED_ORIGINS = [
    "http://localhost:5173",      # Vite dev server
    "http://localhost:3000",      # Alternate dev port
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    # Production domains will be added later:
    # "https://proctorvision.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket handler (shared instance) ---
ws_handler = WebSocketHandler()


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
    """
    Download a PDF integrity report for a completed session.

    Args:
        session_id: The session UUID returned at session start.

    Returns:
        PDF file as downloadable attachment.
    """
    if session_id not in session_store:
        return JSONResponse(
            {"error": "Session not found"},
            status_code=404,
        )

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
    """
    WebSocket endpoint for real-time frame processing.

    Protocol:
    1. Client connects
    2. Client sends { "type": "session_start" }
    3. Server starts calibration phase (10 seconds)
    4. Client streams frames: { "type": "frame", "data": "<base64>", "timestamp": <ms> }
    5. Server streams back violations, risk scores, calibration updates
    6. Client sends { "type": "session_end" } to finish
    7. Server returns session summary with final risk score
    """
    await ws_handler.handle_connection(websocket)


# --- Startup event ---

@app.on_event("startup")
async def startup_event():
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
