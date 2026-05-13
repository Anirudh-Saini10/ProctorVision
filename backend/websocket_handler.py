
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
        # Registry of live sessions for the proctor console.
        # Shape: {session_id: {
        #   "candidate": str, "code": str, "strictness": str,
        #   "started_at": float, "risk": int, "event_count": int,
        #   "last_event": dict|None, "subscribers": set[WebSocket],
        #   "snapshot_counter": int,
        # }}
        self.live_sessions = {}

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
                    await self._handle_session_start(websocket, pipeline, message)

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

    async def _handle_session_start(self, websocket, pipeline, message=None):
        """Start a new proctoring session.

        Optional client-provided metadata (`candidate_name`, `code`,
        `strictness`) is recorded on the live-session registry so the proctor
        console can display it.
        """
        session_id = pipeline.start_session()
        meta = message or {}
        candidate = meta.get("candidate_name") or "Anonymous"
        code = meta.get("code") or ""
        strictness = meta.get("strictness") or "moderate"

        self.live_sessions[session_id] = {
            "candidate": candidate,
            "code": code,
            "strictness": strictness,
            "started_at": time.time(),
            "risk": 0,
            "event_count": 0,
            "last_event": None,
            "subscribers": set(),
            "snapshot_counter": 0,
        }

        # Remember which session a given student websocket owns
        pipeline._session_id = session_id

        print(f"  [WS] Session started: {session_id[:8]} ({candidate})")

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

        # Send new violations (to student + any proctor subscribers)
        for violation in result["violations"]:
            payload = {"type": "violation", **violation}
            await self._send(websocket, payload)
            await self._fanout_to_subscribers(getattr(pipeline, "_session_id", None), payload)

        # Send risk score update
        await self._send(websocket, {
            "type": "risk_score",
            "score": result["risk_score"],
        })

        # Update live session registry + snapshot fan-out for proctors
        sid = getattr(pipeline, "_session_id", None)
        if sid and sid in self.live_sessions:
            live = self.live_sessions[sid]
            live["risk"] = result["risk_score"]
            if result["violations"]:
                live["event_count"] += len(result["violations"])
                live["last_event"] = result["violations"][-1]
            live["snapshot_counter"] += 1
            # forward a snapshot every 5 frames (~1 fps when streaming at 5 fps)
            if live["snapshot_counter"] % 5 == 0 and live["subscribers"]:
                await self._fanout_to_subscribers(sid, {
                    "type": "snapshot",
                    "session_id": sid,
                    "data": frame_data,
                    "timestamp": timestamp_ms,
                    "risk": result["risk_score"],
                    "face_detected": result["face_detected"],
                })
            # always relay risk score updates
            if live["subscribers"]:
                await self._fanout_to_subscribers(sid, {
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
            # notify any proctor subscribers, then drop the live registry entry
            await self._fanout_to_subscribers(sid, {
                "type": "session_ended",
                "summary": summary,
            })
            self.live_sessions.pop(sid, None)

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

    # --- Proctor relay --------------------------------------------------

    async def _fanout_to_subscribers(self, session_id, payload):
        """Relay a payload to every proctor subscribed to the session.

        Drops dead sockets quietly.
        """
        if not session_id or session_id not in self.live_sessions:
            return
        subs = self.live_sessions[session_id]["subscribers"]
        if not subs:
            return
        dead = []
        for ws in list(subs):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            subs.discard(ws)

    def list_active_sessions(self):
        """Snapshot of live sessions for /api/sessions."""
        out = []
        now = time.time()
        for sid, info in self.live_sessions.items():
            out.append({
                "session_id": sid,
                "candidate": info["candidate"],
                "code": info["code"],
                "strictness": info["strictness"],
                "risk": info["risk"],
                "event_count": info["event_count"],
                "duration_sec": int(now - info["started_at"]),
                "last_event": info["last_event"],
                "status": "live",
            })
        return out

    async def handle_proctor_connection(self, websocket: WebSocket):
        """WS endpoint for the proctor console.

        Protocol:
            client -> { type: 'subscribe', session_id }
            client -> { type: 'unsubscribe' }
            server -> { type: 'snapshot' | 'violation' | 'risk_score' | 'session_ended' }
        """
        await websocket.accept()
        subscribed_sid = None
        try:
            # Send initial active sessions list so the proctor UI can populate
            await self._send(websocket, {
                "type": "active_sessions",
                "sessions": self.list_active_sessions(),
            })

            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                t = msg.get("type")
                if t == "subscribe":
                    sid = msg.get("session_id")
                    if not sid or sid not in self.live_sessions:
                        await self._send(websocket, {
                            "type": "error",
                            "message": "unknown session_id",
                        })
                        continue
                    # detach from previous if any
                    if subscribed_sid and subscribed_sid in self.live_sessions:
                        self.live_sessions[subscribed_sid]["subscribers"].discard(websocket)
                    subscribed_sid = sid
                    self.live_sessions[sid]["subscribers"].add(websocket)
                    info = self.live_sessions[sid]
                    await self._send(websocket, {
                        "type": "subscribed",
                        "session_id": sid,
                        "candidate": info["candidate"],
                        "code": info["code"],
                        "strictness": info["strictness"],
                        "risk": info["risk"],
                    })
                elif t == "unsubscribe":
                    if subscribed_sid and subscribed_sid in self.live_sessions:
                        self.live_sessions[subscribed_sid]["subscribers"].discard(websocket)
                    subscribed_sid = None
                elif t == "list":
                    await self._send(websocket, {
                        "type": "active_sessions",
                        "sessions": self.list_active_sessions(),
                    })
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"  [WS:proctor] error: {e}")
        finally:
            if subscribed_sid and subscribed_sid in self.live_sessions:
                self.live_sessions[subscribed_sid]["subscribers"].discard(websocket)
