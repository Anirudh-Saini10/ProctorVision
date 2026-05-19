
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
import traceback
from fastapi import WebSocket, WebSocketDisconnect

# DB writeback is best-effort: if anything goes wrong (DB locked, schema
# drift, etc.) we log and continue rather than letting the proctoring
# pipeline crash. The in-memory session_store is still the primary
# record for live use.
try:
    from sqlmodel import Session  # type: ignore
    from db import engine
    from models import Attempt, AttemptStatus
    _DB_AVAILABLE = True
except Exception as _db_err:  # pragma: no cover
    print(f"  [WS] DB writeback disabled: {_db_err}")
    _DB_AVAILABLE = False


def _persist_attempt_summary(attempt_id, session_id, summary, force_ended=False):
    """Best-effort: write the integrity summary onto the Attempt row.

    Called from session-end paths. Safe to call without a known
    attempt_id (no-op). Never raises — DB hiccups must not break the
    proctoring path.
    """
    if not _DB_AVAILABLE or not attempt_id:
        return
    try:
        with Session(engine) as db:
            row = db.get(Attempt, int(attempt_id))
            if not row:
                return
            if session_id and not row.proctor_session_id:
                row.proctor_session_id = session_id
            # Only overwrite the summary if we actually have one — we
            # call this on session_start with summary=None just to link
            # the session_id, and we don't want that to clobber a real
            # summary written by a previous in-process attempt.
            if summary is not None:
                row.integrity_summary = summary
            if force_ended and row.status == AttemptStatus.in_progress:
                row.status = AttemptStatus.force_ended
            db.add(row)
            db.commit()
    except Exception as e:
        print(f"  [WS] _persist_attempt_summary failed: {e}")


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
        #   "started_at": float, "last_frame_at": float|None,
        #   "risk": int, "event_count": int,
        #   "last_event": dict|None, "subscribers": set[WebSocket],
        #   "snapshot_counter": int, "candidate_ws": WebSocket,
        #   "last_frame": str|None,
        # }}
        self.live_sessions = {}
        # Ring-buffer of ended sessions for proctor replay. Bounded so a
        # long-running server doesn't grow unbounded. Each entry has all
        # the info the dashboard + monitor needs to render a read-only
        # view (final summary + last cached frame + violation list).
        self.ended_sessions = []
        self.ENDED_SESSIONS_LIMIT = 50
        # If a "live" session hasn't received a frame for this long, the
        # backing WS is presumed dead even though the disconnect handler
        # never fired. We sweep these on every list_sessions call. With
        # candidates streaming at 5 fps, 15s of silence is a very safe
        # threshold — short enough to clear ghost rows from the proctor
        # dashboard quickly, long enough to tolerate a momentary network
        # blip.
        self.LIVE_STALE_TIMEOUT_SEC = 15.0

    async def handle_connection(self, websocket: WebSocket):
        """
        Handle a WebSocket connection for the entire session lifecycle.

        Args:
            websocket: FastAPI WebSocket connection
        """
        # Lazy-import: heavy ML libraries (mediapipe, torch, ultralytics)
        # only load when someone actually opens a proctoring session,
        # not at app startup. This keeps the free-tier container under
        # 512MB RAM during boot.
        pipeline = None
        cv_error = None
        cv_error_detail = None
        try:
            from cv_pipeline import CVPipeline
            pipeline = CVPipeline()
        except Exception as exc:
            cv_error = str(exc)
            cv_error_detail = traceback.format_exc()
            print(f"  [WS] CVPipeline import/init failed: {cv_error}")
            print(cv_error_detail)

        await websocket.accept()
        ws_id = id(websocket)
        if pipeline is not None:
            self.active_sessions[ws_id] = pipeline

        print(f"  [WS] Client connected: {ws_id}")

        if cv_error:
            # Send a short user-facing message + a detail field for
            # diagnostics (visible in browser dev-tools without needing
            # server log access).
            await self._send(websocket, {
                "type": "error",
                "message": "Proctoring engine unavailable — exam can continue without AI monitoring.",
                "detail": cv_error,
            })
            # Keep connection open so client can handle gracefully.
            # We'll still process session_start / session_end for bookkeeping,
            # but skip all frame/tab/audio processing.

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
                    if pipeline is None:
                        # Only send error if we didn't already broadcast it
                        # on connection accept (avoids duplicate banners).
                        payload = {
                            "type": "error",
                            "message": "Proctoring engine unavailable — exam can continue without AI monitoring.",
                        }
                        if cv_error:
                            payload["detail"] = cv_error
                        await self._send(websocket, payload)
                    else:
                        await self._handle_session_start(websocket, pipeline, message)

                elif msg_type == "frame":
                    if pipeline is None:
                        # Silently drop frames when CV is unavailable
                        pass
                    else:
                        await self._handle_frame(websocket, pipeline, message)

                elif msg_type == "tab_switch":
                    if pipeline is None:
                        pass
                    else:
                        await self._handle_tab_switch(websocket, pipeline, message)

                elif msg_type == "audio_activity":
                    if pipeline is None:
                        pass
                    else:
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
            # Clean up — be defensive: a candidate may close their tab,
            # crash, HMR-reload, or otherwise drop the WS without ever
            # sending `session_end`. Previously the only `live_sessions`
            # cleanup path was `_handle_session_end`, which meant ghost
            # rows accumulated on the proctor dashboard whenever a
            # candidate disconnected ungracefully.
            sid = getattr(pipeline, "_session_id", None)
            attempt_id = getattr(pipeline, "_attempt_id", None)
            if pipeline and pipeline._session_active:
                try:
                    summary = pipeline.end_session()
                    if sid:
                        self.session_store[sid] = summary
                        await self._fanout_to_subscribers(sid, {
                            "type": "session_ended",
                            "summary": summary,
                            "reason": "disconnect",
                        })
                    # Best-effort DB persist so the proctor's attempt
                    # list reflects the final integrity score even when
                    # the candidate's tab dies mid-exam.
                    _persist_attempt_summary(attempt_id, sid, summary)
                except Exception as e:
                    print(f"  [WS] error finalising on disconnect: {e}")
            if sid:
                # Archive into ended_sessions so the proctor can still
                # see the session in the dashboard's ENDED filter and
                # open it for replay.
                self._archive_session(
                    sid,
                    summary=self.session_store.get(sid),
                    reason="disconnect",
                )
            if ws_id in self.active_sessions:
                del self.active_sessions[ws_id]

    async def _handle_session_start(self, websocket, pipeline, message=None):
        """Start a new proctoring session.

        Optional client-provided metadata (`candidate_name`, `code`,
        `strictness`) is recorded on the live-session registry so the proctor
        console can display it.
        """
        # Guard against duplicate session_start on the same WebSocket.
        # React 18 StrictMode in dev double-mounts components, so the
        # Calibrate page's startSession() useEffect fires twice — both
        # messages arrive on the same WS. Without this guard the first
        # session_id ends up orphaned in `live_sessions` (no candidate
        # WS pointing at it any more) until the 15s stale-sweep, which
        # is what the user saw as a "ghost" zero-risk ENDED row next
        # to every real session in the proctor dashboard.
        #
        # Same path also handles HMR reloads and any other client that
        # accidentally sends session_start twice — we cleanly archive
        # the previous one as `superseded` and proceed with the new.
        prev_sid = getattr(pipeline, "_session_id", None)
        if prev_sid and prev_sid in self.live_sessions:
            print(f"  [WS] superseding prior session {prev_sid[:8]} on same WS")
            self._archive_session(
                prev_sid,
                summary=self.session_store.get(prev_sid),
                reason="superseded",
            )

        session_id = pipeline.start_session()
        meta = message or {}
        candidate = meta.get("candidate_name") or "Anonymous"
        code = meta.get("code") or ""
        strictness = meta.get("strictness") or "moderate"
        # New: link this proctoring session to a persisted Attempt row
        # if the candidate's frontend started one before opening the WS.
        # Stored on the pipeline so the same id is available on every
        # termination path (clean end, disconnect, force-end, stale).
        attempt_id = meta.get("attempt_id")
        pipeline._attempt_id = attempt_id
        # Eager-link the session_id onto the Attempt right now so the
        # proctor's exam-attempts view shows "in progress" candidates
        # before they finish.
        if attempt_id:
            _persist_attempt_summary(attempt_id, session_id, summary=None)

        # Stash on the pipeline so detector/handler code can vary
        # behaviour without re-fetching from the live_sessions registry.
        # Currently used to gate lip_movement / audio violations behind
        # `strict` mode — proctors of moderate or lenient sessions
        # explicitly tolerate the candidate explaining a question to
        # themselves out loud.
        pipeline.strictness = strictness

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
            # Hold a reference to the candidate's WS so the proctor can
            # send manual flags / force-end. Cleared automatically by
            # the disconnect cleanup path.
            "candidate_ws": websocket,
            # Most recent base64 JPEG frame from this candidate, captured
            # so we can attach an "evidence snapshot" to any violation we
            # fan out to proctor subscribers. This is the simplest way
            # to give proctors visual context for *why* a violation
            # fired without recording continuous video.
            "last_frame": None,
            # Per-violation evidence snapshots, persisted for the duration
            # of the session so the proctor can review them AFTER the
            # session ends (the live fan-out is fire-and-forget; a proctor
            # who opens the monitor late, or opens a finished session,
            # would otherwise see nothing). Capped to avoid unbounded
            # memory growth — at ~50KB per JPEG, 40 entries ≈ 2MB.
            "evidence_snapshots": [],
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

        # Update live session registry + snapshot fan-out for proctors
        sid = getattr(pipeline, "_session_id", None)
        if sid and sid in self.live_sessions:
            live = self.live_sessions[sid]
            live["risk"] = result["risk_score"]
            # Cache the most recent frame so it can be attached to any
            # violation evidence_snapshot the proctor receives below.
            live["last_frame"] = frame_data
            # Used by `_sweep_stale_sessions` to detect candidates whose
            # browsers died without firing onclose.
            live["last_frame_at"] = time.time()
            if result["violations"]:
                live["event_count"] += len(result["violations"])
                live["last_event"] = result["violations"][-1]
            live["snapshot_counter"] += 1
            # Periodic snapshot (~1 fps at 5fps frame stream) — keeps the
            # proctor's preview tile fresh even when nothing is wrong.
            if live["snapshot_counter"] % 5 == 0 and live["subscribers"]:
                await self._fanout_to_subscribers(sid, {
                    "type": "snapshot",
                    "session_id": sid,
                    "data": frame_data,
                    "timestamp": timestamp_ms,
                    "risk": result["risk_score"],
                    "face_detected": result["face_detected"],
                })

        # Send new violations (to student + any proctor subscribers).
        # On every violation we ALSO push an `evidence_snapshot` so the
        # proctor sees the exact frame that triggered the alert — much
        # more useful than waiting for the next periodic snapshot.
        for violation in result["violations"]:
            payload = {"type": "violation", **violation}
            await self._send(websocket, payload)
            await self._fanout_to_subscribers(sid, payload)
            # Build the evidence snapshot for this violation. We
            # PERSIST it on the session entry regardless of whether
            # a proctor is currently subscribed, so the snapshot is
            # available when the session is opened later from the
            # ENDED tab. We also fan it out immediately if anyone
            # is watching live.
            if sid and sid in self.live_sessions:
                snap = {
                    "violation_id": violation.get("id"),
                    "violation_type": violation.get("violation_type"),
                    "data": frame_data,
                    "timestamp": timestamp_ms,
                    "risk": result["risk_score"],
                    "face_detected": result["face_detected"],
                }
                self._store_evidence_snapshot(sid, snap)
                if self.live_sessions[sid]["subscribers"]:
                    await self._fanout_to_subscribers(sid, {
                        "type": "evidence_snapshot",
                        **snap,
                    })

        # Send risk score update (to student + any proctor subscribers)
        await self._send(websocket, {
            "type": "risk_score",
            "score": result["risk_score"],
        })
        if sid and sid in self.live_sessions and self.live_sessions[sid]["subscribers"]:
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
            vd = v.to_dict()
            await self._send(websocket, {
                "type": "violation",
                **vd,
            })
            # Persist + relay an evidence snapshot using whatever the
            # candidate last sent us. Tab switches don't naturally come
            # with a frame; reusing `last_frame` shows the proctor what
            # was on screen just before the focus loss, which is often
            # the most useful possible visual evidence.
            sid = getattr(pipeline, "_session_id", None)
            if sid and sid in self.live_sessions:
                last = self.live_sessions[sid].get("last_frame")
                if last:
                    snap = {
                        "violation_id": vd.get("id"),
                        "violation_type": vd.get("violation_type"),
                        "data": last,
                        "timestamp": timestamp,
                        "risk": pipeline.violation_logger.get_risk_score(),
                        "face_detected": True,
                    }
                    self._store_evidence_snapshot(sid, snap)
                    await self._fanout_to_subscribers(sid, {
                        "type": "evidence_snapshot",
                        **snap,
                    })
                await self._fanout_to_subscribers(sid, {
                    "type": "violation",
                    **vd,
                })

            await self._send(websocket, {
                "type": "risk_score",
                "score": pipeline.violation_logger.get_risk_score(),
            })

    async def _handle_audio_activity(self, websocket, pipeline, message):
        """
        Handle audio activity detection from the browser.

        The frontend hook (`useAudioActivity`) has already:
          - measured sustained speech above an RMS threshold
          - enforced a minimum speaking duration (~450ms)
          - rate-limited to one event per speaking burst

        So by the time we get here it's already a high-confidence
        "student is talking" event. We trust it — the frontend did the
        sustained filtering, and we just need to log it.

        Previously this handler divided `audio_level` through
        `confidence = audio_level * 2`, which typically produced
        confidence ≈ 0.2-0.4 for normal speech — below the logger's
        MIN_CONFIDENCE gate of 0.65 — so audio events got silently
        dropped. We now publish a fixed 0.9 confidence and let the
        violation_logger's cooldown handle rate limiting.
        """
        is_speaking = message.get("is_speaking", False)
        audio_level = float(message.get("audio_level", 0.0))

        if not is_speaking:
            return

        # STRICTNESS GATE: speaking detection is a strict-only feature.
        # In moderate / lenient sessions the proctor has explicitly
        # accepted that the candidate may talk to themselves while
        # working through a question. Frontend already avoids opening
        # the mic in non-strict mode; this is defence-in-depth so a
        # forged client can't push fake speech events.
        if getattr(pipeline, "strictness", "moderate") != "strict":
            return

        # COMBINED GATE: audio alone is wildly unreliable — chair scrape,
        # keyboard clack, AC kicking on, dog bark, sibling shouting from
        # the next room all push the mic RMS above threshold. We only
        # log a `lip_movement` violation when the audio burst is
        # corroborated by the lips actually moving on camera.
        #
        # `is_mouth_active()` looks at the last ~10 frames of MAR
        # samples and returns True if the mouth was either parted
        # (MAR > 0.18) or visibly moving (variance > tiny threshold).
        # This destroys 99% of environmental-noise false positives
        # while still catching whispering (low MAR but high variance).
        if not pipeline.lip_detector.is_mouth_active():
            print(f"  [WS] audio burst suppressed — mouth was still "
                  f"(audio_level={audio_level:.3f})")
            return

        v = pipeline.violation_logger.log_violation(
            "lip_movement",
            confidence=0.95,
            metadata={
                "source": "audio+lip",
                "audio_level": round(audio_level, 3),
            },
        )
        if v:
            vd = v.to_dict()
            payload = {"type": "violation", **vd}
            await self._send(websocket, payload)
            sid = getattr(pipeline, "_session_id", None)
            await self._fanout_to_subscribers(sid, payload)
            # Attach last-known frame so the proctor sees what the
            # candidate looked like during the audio burst.
            if sid and sid in self.live_sessions:
                last = self.live_sessions[sid].get("last_frame")
                if last:
                    snap = {
                        "violation_id": vd.get("id"),
                        "violation_type": vd.get("violation_type"),
                        "data": last,
                        "timestamp": int(time.time() * 1000),
                        "risk": pipeline.violation_logger.get_risk_score(),
                        "face_detected": True,
                    }
                    self._store_evidence_snapshot(sid, snap)
                    await self._fanout_to_subscribers(sid, {
                        "type": "evidence_snapshot",
                        **snap,
                    })
            risk = pipeline.violation_logger.get_risk_score()
            await self._send(websocket, {"type": "risk_score", "score": risk})
            await self._fanout_to_subscribers(sid, {"type": "risk_score", "score": risk})

    async def _handle_session_end(self, websocket, pipeline):
        """End the current proctoring session."""
        if pipeline is None:
            await self._send(websocket, {
                "type": "session_ended",
                "summary": {"risk_score": 0, "violation_counts": {}, "total_events": 0, "reason": "no_cv_engine"},
            })
            return
        summary = pipeline.end_session()
        print(f"  [WS] Session ended. Risk score: {summary['risk_score']}")

        # Persist summary so /api/report/{session_id} can serve a PDF,
        # and write back onto the persisted Attempt row so the proctor
        # dashboard reflects the final integrity score.
        sid = summary.get("session_id")
        attempt_id = getattr(pipeline, "_attempt_id", None)
        _persist_attempt_summary(attempt_id, sid, summary)
        if sid:
            self.session_store[sid] = summary
            # notify any proctor subscribers, then drop the live registry entry
            await self._fanout_to_subscribers(sid, {
                "type": "session_ended",
                "summary": summary,
            })
            # Archive — keeps the session visible to the proctor under
            # the ENDED filter with full summary + last frame for replay.
            self._archive_session(sid, summary=summary, reason="clean")

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

    # --- Lifecycle bookkeeping ------------------------------------------

    # Hard cap on persisted evidence snapshots per session. Each is a
    # base64 JPEG (~50KB), so 40 entries ≈ 2MB worst case. If the
    # candidate goes wild and triggers more, we keep the most recent.
    EVIDENCE_SNAPSHOT_LIMIT = 40

    def _store_evidence_snapshot(self, session_id, snap):
        """Append a violation-evidence snapshot to the live session and
        trim to the cap. Safe to call when subscribers list is empty —
        we persist regardless of who is watching, because the whole
        point is to make the evidence available *after* the fact.
        """
        live = self.live_sessions.get(session_id)
        if not live:
            return
        bucket = live.setdefault("evidence_snapshots", [])
        bucket.append(snap)
        if len(bucket) > self.EVIDENCE_SNAPSHOT_LIMIT:
            del bucket[: len(bucket) - self.EVIDENCE_SNAPSHOT_LIMIT]

    def _archive_session(self, session_id, summary, reason):
        """Move a session out of `live_sessions` and into `ended_sessions`.

        Idempotent — safe to call multiple times for the same session_id
        (e.g. once from `_handle_session_end` and once from the disconnect
        cleanup `finally:` block; whichever runs first wins).

        The archived entry is what the proctor dashboard's ENDED filter
        and the proctor monitor's "replay" mode read from. It carries:
          - all the live-registry fields the dashboard renders
          - the final summary dict (violations, risk_score, integrity, ...)
          - the very last cached camera frame, so the monitor has
            visual evidence to display in the replay view
          - a `reason` tag explaining how it ended ("clean" / "disconnect" /
            "stale" / "force_end") for debugging.

        Returns the archived entry, or None if the session_id wasn't
        live.
        """
        live = self.live_sessions.pop(session_id, None)
        if not live:
            return None
        if any(e["session_id"] == session_id for e in self.ended_sessions):
            return None
        entry = {
            "session_id": session_id,
            "candidate": live.get("candidate", "Anonymous"),
            "code": live.get("code", ""),
            "strictness": live.get("strictness", "moderate"),
            "started_at": live.get("started_at"),
            "ended_at": time.time(),
            "duration_sec": int(time.time() - (live.get("started_at") or time.time())),
            "final_risk": (summary or {}).get("peak_risk", live.get("risk", 0)),
            "event_count": live.get("event_count", 0),
            "last_event": live.get("last_event"),
            "last_frame": live.get("last_frame"),
            "evidence_snapshots": live.get("evidence_snapshots", []),
            "summary": summary or {},
            "subscribers": live.get("subscribers", set()),
            "ended_reason": reason,
        }
        self.ended_sessions.append(entry)
        # Drop oldest if over cap
        if len(self.ended_sessions) > self.ENDED_SESSIONS_LIMIT:
            self.ended_sessions = self.ended_sessions[-self.ENDED_SESSIONS_LIMIT:]
        return entry

    def _sweep_stale_sessions(self):
        """Move any live session with no recent frames to ended_sessions.

        Defensive: if a candidate's browser dies in a way that doesn't
        trigger our disconnect handler (force-quit, OS sleep, etc.), the
        live registry would otherwise show them as LIVE forever. This
        is called from `list_active_sessions` so the dashboard self-heals
        every poll.
        """
        now = time.time()
        stale_ids = []
        for sid, info in list(self.live_sessions.items()):
            last_seen = info.get("last_frame_at") or info.get("started_at") or now
            if now - last_seen > self.LIVE_STALE_TIMEOUT_SEC:
                stale_ids.append(sid)
        for sid in stale_ids:
            print(f"  [WS] sweeping stale session: {sid[:8]}")
            # Best-effort summary — the pipeline may already be gone.
            self._archive_session(sid, summary=None, reason="stale")

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
        """Snapshot of live + ended sessions for /api/sessions and the
        proctor dashboard.

        Self-healing: each call sweeps any "live" entry whose backing WS
        has gone silent (`_sweep_stale_sessions`) so ghost rows can't
        accumulate even when the disconnect handler fails to fire.

        Returns a list of dicts with `status: "live" | "ended"`. The
        dashboard filters by status to render the LIVE / ENDED tabs.
        """
        # Self-heal first so the list we return is accurate.
        self._sweep_stale_sessions()

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
        # Most-recent ended first so the dashboard naturally shows fresh
        # endings at the top. Hide `superseded` entries — these are the
        # double-mount artefacts archived by `_handle_session_start`'s
        # dedup guard. They carry no useful information for the proctor.
        for entry in reversed(self.ended_sessions):
            if entry.get("ended_reason") == "superseded":
                continue
            out.append({
                "session_id": entry["session_id"],
                "candidate": entry["candidate"],
                "code": entry["code"],
                "strictness": entry["strictness"],
                "risk": entry["final_risk"],
                "event_count": entry["event_count"],
                "duration_sec": entry["duration_sec"],
                "last_event": entry["last_event"],
                "ended_at": entry["ended_at"],
                "ended_reason": entry["ended_reason"],
                "status": "ended",
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
                    # detach from previous (live) if any
                    if subscribed_sid and subscribed_sid in self.live_sessions:
                        self.live_sessions[subscribed_sid]["subscribers"].discard(websocket)
                    subscribed_sid = sid

                    if sid and sid in self.live_sessions:
                        # ── live subscribe: stream realtime events ───────
                        self.live_sessions[sid]["subscribers"].add(websocket)
                        info = self.live_sessions[sid]
                        await self._send(websocket, {
                            "type": "subscribed",
                            "session_id": sid,
                            "candidate": info["candidate"],
                            "code": info["code"],
                            "strictness": info["strictness"],
                            "risk": info["risk"],
                            "ended": False,
                        })
                        # Push the cached last frame immediately so the
                        # snapshot tile doesn't stay on "awaiting first
                        # frame" until the next 1fps tick.
                        if info.get("last_frame"):
                            await self._send(websocket, {
                                "type": "snapshot",
                                "session_id": sid,
                                "data": info["last_frame"],
                                "timestamp": int(time.time() * 1000),
                                "risk": info["risk"],
                                "face_detected": True,
                            })
                        # Backfill every evidence snapshot collected so
                        # far. This is what lets a proctor who joins
                        # mid-session see violations that already fired.
                        for snap in info.get("evidence_snapshots", []):
                            await self._send(websocket, {
                                "type": "evidence_snapshot",
                                **snap,
                            })
                        continue

                    # ── ended-session replay ─────────────────────────────
                    archived = next(
                        (e for e in self.ended_sessions
                         if e["session_id"] == sid),
                        None,
                    )
                    if not archived:
                        await self._send(websocket, {
                            "type": "error",
                            "message": "unknown session_id",
                        })
                        subscribed_sid = None
                        continue

                    summary = archived.get("summary") or {}
                    await self._send(websocket, {
                        "type": "subscribed",
                        "session_id": sid,
                        "candidate": archived["candidate"],
                        "code": archived["code"],
                        "strictness": archived["strictness"],
                        "risk": archived["final_risk"],
                        "ended": True,
                        "ended_reason": archived["ended_reason"],
                    })
                    # Last frame as the snapshot
                    if archived.get("last_frame"):
                        await self._send(websocket, {
                            "type": "snapshot",
                            "session_id": sid,
                            "data": archived["last_frame"],
                            "timestamp": int((archived.get("ended_at") or time.time()) * 1000),
                            "risk": archived["final_risk"],
                            "face_detected": True,
                        })
                    # Replay all violations as event-stream entries
                    for v in summary.get("violations", []):
                        await self._send(websocket, {
                            "type": "violation",
                            **v,
                        })
                    # Replay each persisted evidence snapshot so the
                    # proctor has the actual frames that triggered the
                    # phone / multi-face / face-absence alerts — not
                    # just the final cached one.
                    for snap in archived.get("evidence_snapshots", []):
                        await self._send(websocket, {
                            "type": "evidence_snapshot",
                            **snap,
                        })
                    # Final summary so the Monitor renders the
                    # session-ended banner and Final risk gauge.
                    await self._send(websocket, {
                        "type": "session_ended",
                        "summary": summary,
                        "reason": archived["ended_reason"],
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
                elif t == "manual_flag":
                    # Proctor manually logs a violation for the subscribed
                    # session. Note arrives as `note` (free text). Logged
                    # as `manual_flag` violation type — students still see
                    # it in their event stream, and it appears in the
                    # final report just like an automated detection.
                    target = msg.get("session_id") or subscribed_sid
                    note = (msg.get("note") or "").strip() or "Manually flagged by proctor"
                    if not target or target not in self.live_sessions:
                        await self._send(websocket, {
                            "type": "error", "message": "no live session to flag",
                        })
                        continue
                    target_ws = self.live_sessions[target].get("candidate_ws")
                    pipeline = self.active_sessions.get(id(target_ws)) if target_ws else None
                    if not pipeline:
                        await self._send(websocket, {
                            "type": "error", "message": "candidate pipeline gone",
                        })
                        continue
                    v = pipeline.violation_logger.log_violation(
                        "manual_flag",
                        confidence=1.0,
                        metadata={"note": note, "source": "proctor"},
                    )
                    if v:
                        vd = v.to_dict()
                        payload = {"type": "violation", **vd}
                        # to candidate
                        await self._send(target_ws, payload)
                        # to all subscribed proctors (including this one)
                        await self._fanout_to_subscribers(target, payload)
                        # Persist evidence using the last cached frame
                        # so the proctor's own manual flag is also
                        # backed by a visual record.
                        last = self.live_sessions[target].get("last_frame")
                        if last:
                            snap = {
                                "violation_id": vd.get("id"),
                                "violation_type": vd.get("violation_type"),
                                "data": last,
                                "timestamp": int(time.time() * 1000),
                                "risk": pipeline.violation_logger.get_risk_score(),
                                "face_detected": True,
                            }
                            self._store_evidence_snapshot(target, snap)
                            await self._fanout_to_subscribers(target, {
                                "type": "evidence_snapshot",
                                **snap,
                            })
                        # bump risk for everyone
                        risk = pipeline.violation_logger.get_risk_score()
                        await self._send(target_ws, {"type": "risk_score", "score": risk})
                        await self._fanout_to_subscribers(target, {
                            "type": "risk_score", "score": risk,
                        })
                elif t == "force_end":
                    # Proctor force-ends the candidate's session. The
                    # candidate's frontend will receive a `force_end`
                    # message, finalise locally, and navigate to Done.
                    # We do NOT call end_session here — we let the
                    # candidate WS go through its normal session_end
                    # flow so the summary path stays consistent.
                    target = msg.get("session_id") or subscribed_sid
                    if not target or target not in self.live_sessions:
                        await self._send(websocket, {
                            "type": "error", "message": "no live session to end",
                        })
                        continue
                    target_ws = self.live_sessions[target].get("candidate_ws")
                    if target_ws:
                        await self._send(target_ws, {
                            "type": "force_end",
                            "reason": msg.get("reason") or "Ended by proctor",
                        })
                    # Mark the attempt as force-ended in the DB right
                    # away. The candidate's WS will (eventually) fire
                    # session_end and that path will overwrite the
                    # final integrity_summary; this just makes sure the
                    # status reflects "force_ended" even if they never
                    # come back.
                    target_pipeline = self.active_sessions.get(id(target_ws)) if target_ws else None
                    target_attempt_id = getattr(target_pipeline, "_attempt_id", None) if target_pipeline else None
                    _persist_attempt_summary(
                        target_attempt_id, target, summary=None, force_ended=True,
                    )
                    await self._send(websocket, {
                        "type": "force_end_ack", "session_id": target,
                    })
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"  [WS:proctor] error: {e}")
        finally:
            if subscribed_sid and subscribed_sid in self.live_sessions:
                self.live_sessions[subscribed_sid]["subscribers"].discard(websocket)
