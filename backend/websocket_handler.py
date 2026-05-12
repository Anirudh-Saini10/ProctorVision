"""
ProctorVision — WebSocket Handler
====================================
WebSocket endpoint that receives frames from the browser, dispatches
them to the CV pipeline, and streams violation events back in real time.

Message Schema:
    Client → Server:
        { "type": "frame", "data": "<base64 JPEG>", "timestamp": <ms> }
        { "type": "tab_switch", "timestamp": <ms>, "direction": "blur"|"hidden" }
        { "type": "session_start" }
        { "type": "session_end" }

    Server → Client:
        { "type": "violation", "violation_type": "<str>", "confidence": <float>, "timestamp": <ms>, "bbox": [x,y,w,h]|null }
        { "type": "risk_score", "score": <int 0-100> }
        { "type": "calibration_progress", "progress": <float 0-1>, "remaining": <float>, "state": "<str>" }
        { "type": "calibration_complete" }
        { "type": "session_started", "session_id": "<uuid>" }
        { "type": "session_ended", "summary": { ... } }
        { "type": "frame_processed", "frame_number": <int>, "face_detected": <bool> }
        { "type": "error", "message": "<str>" }
"""

import json
import time
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from cv_pipeline import CVPipeline


class WebSocketHandler:
    """
    Manages WebSocket connections for proctoring sessions.

    Each connected client gets their own CVPipeline instance.
    Frames are processed asynchronously, and results are streamed back.
    """

    def __init__(self, session_store=None):
        self.active_sessions = {}  # {websocket_id: CVPipeline}
        # Shared dict (session_id -> summary) used by the /api/report endpoint.
        self.session_store = session_store if session_store is not None else {}

    async def handle_connection(self, websocket: WebSocket):
        """
        Handle a WebSocket connection for the entire session lifecycle.

        Args:
            websocket: FastAPI WebSocket connection
        """
        await websocket.accept()
        ws_id = id(websocket)
        pipeline = CVPipeline()
        self.active_sessions[ws_id] = pipeline

        print(f"  [WS] Client connected: {ws_id}")

        try:
            while True:
                # Receive message from client
                raw_message = await websocket.receive_text()

                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    await self._send(websocket, {
                        "type": "error",
                        "message": "Invalid JSON message",
                    })
                    continue

                msg_type = message.get("type")

                if msg_type == "session_start":
                    await self._handle_session_start(websocket, pipeline)

                elif msg_type == "frame":
                    await self._handle_frame(websocket, pipeline, message)

                elif msg_type == "tab_switch":
                    await self._handle_tab_switch(websocket, pipeline, message)

                elif msg_type == "audio_activity":
                    await self._handle_audio_activity(websocket, pipeline, message)

                elif msg_type == "session_end":
                    await self._handle_session_end(websocket, pipeline)

                else:
                    await self._send(websocket, {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })

        except WebSocketDisconnect:
            print(f"  [WS] Client disconnected: {ws_id}")
        except Exception as e:
            print(f"  [WS] Error for client {ws_id}: {e}")
        finally:
            # Clean up
            if pipeline._session_active:
                pipeline.end_session()
            if ws_id in self.active_sessions:
                del self.active_sessions[ws_id]

    async def _handle_session_start(self, websocket, pipeline):
        """Start a new proctoring session."""
        session_id = pipeline.start_session()
        print(f"  [WS] Session started: {session_id[:8]}")

        await self._send(websocket, {
            "type": "session_started",
            "session_id": session_id,
        })

        # Send initial calibration progress
        await self._send(websocket, {
            "type": "calibration_progress",
            **pipeline.calibration.get_progress(),
        })

    async def _handle_frame(self, websocket, pipeline, message):
        """
        Process a frame from the client.

        Runs the CV pipeline and sends back any violations and updates.
        """
        frame_data = message.get("data")
        timestamp_ms = message.get("timestamp")

        if not frame_data:
            return

        # Process frame through CV pipeline (CPU-bound, run in thread pool)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, pipeline.process_frame, frame_data, timestamp_ms
        )

        if "error" in result:
            await self._send(websocket, {
                "type": "error",
                "message": result["error"],
            })
            return

        # Send new violations
        for violation in result["violations"]:
            await self._send(websocket, {
                "type": "violation",
                **violation,
            })

        # Send risk score update (only when it changes)
        await self._send(websocket, {
            "type": "risk_score",
            "score": result["risk_score"],
        })

        # Send calibration updates
        cal = result["calibration"]
        if cal["state"] == "calibrating":
            await self._send(websocket, {
                "type": "calibration_progress",
                **cal,
            })
        elif cal["state"] == "complete":
            # Send calibration complete once
            if not hasattr(pipeline, '_cal_complete_sent') or not pipeline._cal_complete_sent:
                pipeline._cal_complete_sent = True
                await self._send(websocket, {
                    "type": "calibration_complete",
                })

        # Send lightweight frame processed acknowledgement
        await self._send(websocket, {
            "type": "frame_processed",
            "frame_number": result["frame_number"],
            "face_detected": result["face_detected"],
            "face_count": result["face_count"],
        })

    async def _handle_tab_switch(self, websocket, pipeline, message):
        """Handle a tab switch / focus loss event from the browser."""
        direction = message.get("direction", "blur")
        timestamp = message.get("timestamp", int(time.time() * 1000))

        # Log as violation
        v = pipeline.violation_logger.log_violation(
            "tab_switch",
            confidence=1.0,  # Browser events are 100% reliable
            metadata={"direction": direction, "source": "browser"},
        )

        if v:
            await self._send(websocket, {
                "type": "violation",
                **v.to_dict(),
            })

            await self._send(websocket, {
                "type": "risk_score",
                "score": pipeline.violation_logger.get_risk_score(),
            })

    async def _handle_audio_activity(self, websocket, pipeline, message):
        """
        Handle audio activity detection from the browser.

        The frontend sends audio level data which can be combined
        with MAR for more accurate speech detection.
        """
        is_speaking = message.get("is_speaking", False)
        audio_level = message.get("audio_level", 0.0)

        # For now, store on pipeline for the lip detector to use
        # Full audio-based violation logic will be integrated in frontend phase
        if is_speaking and audio_level > 0.1:
            v = pipeline.violation_logger.log_violation(
                "lip_movement",
                confidence=min(1.0, audio_level * 2),
                metadata={"source": "audio", "audio_level": audio_level},
            )
            if v:
                await self._send(websocket, {
                    "type": "violation",
                    **v.to_dict(),
                })
                await self._send(websocket, {
                    "type": "risk_score",
                    "score": pipeline.violation_logger.get_risk_score(),
                })

    async def _handle_session_end(self, websocket, pipeline):
        """End the current proctoring session."""
        summary = pipeline.end_session()
        print(f"  [WS] Session ended. Risk score: {summary['risk_score']}")

        # Persist summary so /api/report/{session_id} can serve a PDF.
        sid = summary.get("session_id")
        if sid:
            self.session_store[sid] = summary

        await self._send(websocket, {
            "type": "session_ended",
            "summary": summary,
        })

    @staticmethod
    async def _send(websocket: WebSocket, data: dict):
        """Send a JSON message to the client."""
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            pass  # Client may have disconnected
