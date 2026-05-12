"""
ProctorVision — End-to-end WebSocket gaze-violation test (manual, webcam-based).

What it does:
  1. Opens your default webcam.
  2. Connects to ws://127.0.0.1:8000/ws.
  3. Sends session_start.
  4. Streams JPEG frames at ~6 FPS.
  5. Prints every server message (calibration progress, violations, risk score).
  6. Highlights gaze_deviation events in green/red.
  7. Sends session_end after the configured runtime (default 40s) or when you press 'q'.
  8. Saves the session_id so you can hit /api/report/{session_id} afterwards.

Instructions while it runs:
  - For the first ~10s: LOOK STRAIGHT AT THE CAMERA (calibration).
  - After "calibration_complete": deliberately LOOK LEFT or RIGHT for >2s.
  - You should see a `gaze_deviation` violation appear and risk_score drop.
"""

import asyncio
import base64
import json
import sys
import time

import cv2
import websockets

WS_URL = "ws://127.0.0.1:8000/ws"
TARGET_FPS = 6
DURATION_SEC = 45
JPEG_QUALITY = 70


async def run():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: cannot open webcam"); sys.exit(1)

    print(f"Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL, max_size=8 * 1024 * 1024) as ws:
        print("Connected.")

        session_id = None
        gaze_violations = 0
        last_risk = 100
        cal_done = False

        async def reader():
            nonlocal session_id, gaze_violations, last_risk, cal_done
            async for raw in ws:
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "session_started":
                    session_id = msg["session_id"]
                    print(f"[session_started] {session_id}")
                elif t == "calibration_progress":
                    p = msg.get("progress", 0)
                    print(f"[calibration] {p*100:5.1f}%  state={msg.get('state')}")
                elif t == "calibration_complete":
                    cal_done = True
                    print("\n*** CALIBRATION COMPLETE — now look LEFT or RIGHT for >2 seconds ***\n")
                elif t == "violation":
                    vt = msg.get("violation_type")
                    conf = msg.get("confidence", 0)
                    meta = msg.get("metadata", {})
                    tag = "  >>> " if vt == "gaze_deviation" else "      "
                    if vt == "gaze_deviation":
                        gaze_violations += 1
                    print(f"{tag}[VIOLATION] {vt}  conf={conf:.2f}  meta={meta}")
                elif t == "risk_score":
                    s = msg["score"]
                    if s != last_risk:
                        last_risk = s
                        print(f"[risk_score] {s}/100")
                elif t == "session_ended":
                    print(f"[session_ended] summary keys: {list(msg['summary'].keys())}")
                elif t == "error":
                    print(f"[ERROR] {msg.get('message')}")
                # ignore frame_processed acks (noisy)

        reader_task = asyncio.create_task(reader())

        # session_start
        await ws.send(json.dumps({"type": "session_start"}))

        # stream frames
        start = time.time()
        next_send = start
        frame_interval = 1.0 / TARGET_FPS
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

        try:
            while time.time() - start < DURATION_SEC:
                ok, frame = cap.read()
                if not ok:
                    continue

                # Mirror for natural feel
                frame = cv2.flip(frame, 1)

                now = time.time()
                if now >= next_send:
                    ok2, buf = cv2.imencode(".jpg", frame, encode_params)
                    if ok2:
                        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                        await ws.send(json.dumps({
                            "type": "frame",
                            "data": b64,
                            "timestamp": int(now * 1000),
                        }))
                    next_send = now + frame_interval

                # Local preview
                label = "CALIBRATING — look at camera" if not cal_done else "Look left/right for >2s to trigger gaze violation"
                cv2.putText(frame, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0, 255, 0) if cal_done else (0, 200, 255), 2)
                cv2.putText(frame, f"risk={last_risk}  gaze_viol={gaze_violations}",
                            (10, frame.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.imshow("ProctorVision WS gaze test (press q to end early)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                await asyncio.sleep(0.005)
        finally:
            cap.release()
            cv2.destroyAllWindows()

            await ws.send(json.dumps({"type": "session_end"}))
            try:
                await asyncio.wait_for(asyncio.sleep(1.5), timeout=2.0)
            except Exception:
                pass
            reader_task.cancel()

        print("\n========== RESULT ==========")
        print(f"session_id:        {session_id}")
        print(f"gaze_violations:   {gaze_violations}")
        print(f"final_risk_score:  {last_risk}/100")
        print(f"calibration_done:  {cal_done}")
        print(f"PDF check (after backend stores summary): curl http://127.0.0.1:8000/api/report/{session_id} -o test_report.pdf")


if __name__ == "__main__":
    asyncio.run(run())
