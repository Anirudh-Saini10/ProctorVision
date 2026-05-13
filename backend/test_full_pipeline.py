"""
ProctorVision — Full Pipeline Diagnostic (LOCAL, no WebSocket).

Runs every detector in cv_pipeline.CVPipeline against your live webcam and
overlays every signal on screen at once:

    - Calibration progress / state
    - Gaze: h_dev, v_dev, dir, viol (only after head-forward gate)
    - Head pose: yaw/pitch deviation, dir, viol
    - Lip movement: MAR, viol
    - YOLO objects: bounding boxes drawn on frame (phone / book / person / etc.)
    - Multi-face: face_count
    - Earpiece: detected flag
    - Running risk score + last-5-violations log
    - Flag timeline strip at the bottom (colour-coded, scrolls with time)

Use this as the ground-truth "does everything work together" test before we
start frontend work.

Behaviour checklist to run through (roughly 5 minutes total):

    1. First 10 s — calibration. Sit still, look at camera.
    2. Calm sit, looking straight      (expect: 0 violations)
    3. Deliberate eye-only LEFT / RIGHT for 2s each   (expect: gaze_deviation)
    4. Deliberate head turn L / R for 3s              (expect: head_pose)
    5. Speak normally for 4 s                         (expect: lip_movement)
    6. Big yawn, eyes close, mouth open ~2 s          (we want: NO violation)
    7. Look down at desk for 5 s                      (observe what fires)
    8. Pretend to write on paper: head down 15 s      (observe what fires)
    9. Hold phone up in frame 3 s                     (expect: phone_detected)
   10. Hold open book in frame 3 s                    (expect: book_detected)
   11. Have a second face briefly in frame            (expect: multiple_faces)
   12. Cover face entirely for 3 s                    (expect: face_absent)

Press 'q' to quit. Summary prints at end, including which detectors fired
at least once and the max of each signal.
"""

import time
from collections import deque

import cv2
import numpy as np

from cv_pipeline import CVPipeline
from gaze_estimator import HORIZONTAL_THRESHOLD as GAZE_H, VERTICAL_THRESHOLD as GAZE_V
from head_pose_estimator import YAW_THRESHOLD, PITCH_THRESHOLD
from lip_movement_detector import MAR_THRESHOLD


# ---------- styling helpers ----------
WHITE = (255, 255, 255)
GREY = (170, 170, 170)
GREEN = (80, 220, 100)
AMBER = (0, 165, 255)
RED = (0, 0, 255)
CYAN = (220, 220, 0)
BLUE = (255, 150, 0)

VIOL_COLOURS = {
    # hard
    "phone_detected": RED,
    "book_detected": RED,
    "multiple_faces": RED,
    "face_absent": RED,
    "earpiece_detected": RED,
    # soft
    "gaze_deviation": AMBER,
    "head_pose": AMBER,
    "lip_movement": AMBER,
    # info
    "tab_switch": BLUE,
}


def fmt(v, w=6):
    if v is None:
        return " " * w
    try:
        return f"{v:+.2f}".rjust(w)
    except Exception:
        return str(v).rjust(w)


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: cannot open webcam")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

    pipeline = CVPipeline()
    session_id = pipeline.start_session()
    print(f"session_id = {session_id}")
    print(f"thresholds: gaze H={GAZE_H} V={GAZE_V}  "
          f"head yaw={YAW_THRESHOLD} pitch={PITCH_THRESHOLD}  "
          f"MAR={MAR_THRESHOLD}")

    # rolling state for the diagnostic
    timeline = deque(maxlen=200)          # (wall_time, type) tuples for bottom strip
    recent_violations = deque(maxlen=5)   # most-recent-first list
    fired_types = set()                   # which detectors fired at least once
    max_signals = {                       # max observed values for summary
        "gaze_h": 0.0, "gaze_v": 0.0,
        "yaw_dev": 0.0, "pitch_dev": 0.0,
        "mar": 0.0,
    }
    start_time = time.time()
    last_print = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        frame = cv2.flip(frame, 1)  # mirror for natural feel
        h, w = frame.shape[:2]

        result = pipeline.process_frame(frame)

        cal = result.get("calibration") or {}
        cal_state = cal.get("state", "?")
        cal_progress = cal.get("progress", 0.0)

        gaze = result.get("gaze") or {}
        hp = result.get("head_pose") or {}
        lip = result.get("lip_movement") or {}
        objs = result.get("objects") or {"detections": [], "person_count": 0}
        face_count = result.get("face_count", 0)
        face_detected = result.get("face_detected", False)
        degraded = result.get("degraded", False)
        risk = result.get("risk_score", 100)
        new_violations = result.get("violations", [])

        # Track max signals while head forward (for clean numbers)
        hp_dev = hp.get("deviation")
        yaw_dev = float(hp_dev[1]) if hp_dev is not None else None
        pitch_dev = float(hp_dev[0]) if hp_dev is not None else None
        head_forward = (
            yaw_dev is not None and pitch_dev is not None
            and abs(yaw_dev) < 15 and abs(pitch_dev) < 15
        )
        gdev = gaze.get("deviation")
        if head_forward and gdev is not None:
            max_signals["gaze_h"] = max(max_signals["gaze_h"], abs(float(gdev[0])))
            max_signals["gaze_v"] = max(max_signals["gaze_v"], abs(float(gdev[1])))
        if yaw_dev is not None:
            max_signals["yaw_dev"] = max(max_signals["yaw_dev"], abs(yaw_dev))
        if pitch_dev is not None:
            max_signals["pitch_dev"] = max(max_signals["pitch_dev"], abs(pitch_dev))
        if lip.get("mar") is not None:
            max_signals["mar"] = max(max_signals["mar"], float(lip["mar"]))

        # Record new violations
        now = time.time()
        for v in new_violations:
            vt = v.get("violation_type") or v.get("type") or "unknown"
            timeline.append((now, vt))
            recent_violations.appendleft((now, vt, v.get("confidence", 0.0), v.get("metadata", {})))
            fired_types.add(vt)

        # ---------- DRAW YOLO BOXES ON THE FRAME ----------
        for det in objs.get("detections", []):
            x1, y1, x2, y2 = det["bbox"]
            cls = det["class_name"]
            conf = det["confidence"]
            is_v = det.get("is_violation", False)
            colour = RED if is_v else GREEN
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
            label = f"{cls} {conf:.2f}"
            cv2.putText(frame, label, (x1, max(18, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1, cv2.LINE_AA)

        # ---------- LEFT-SIDE OVERLAY TEXT ----------
        line_y = 22

        def put(txt, colour=WHITE, size=0.5):
            nonlocal line_y
            cv2.putText(frame, txt, (8, line_y), cv2.FONT_HERSHEY_SIMPLEX,
                        size, colour, 1, cv2.LINE_AA)
            line_y += int(18 * (size / 0.5))

        # Header
        if cal_state == "calibrating":
            put(f"CALIBRATING  {cal_progress*100:4.1f}%", AMBER, 0.55)
        elif cal_state == "complete":
            put(f"LIVE  risk={risk}/100   face={face_count}{'  DEGRADED' if degraded else ''}",
                GREEN if risk > 70 else (AMBER if risk > 40 else RED), 0.55)
        else:
            put(f"state={cal_state}")

        put("")
        # Gaze
        gdir = gaze.get("direction", "-")
        gviol = gaze.get("is_violation", False)
        gdur = gaze.get("violation_duration", 0.0)
        hx = gdev[0] if gdev is not None else None
        hy = gdev[1] if gdev is not None else None
        put(f"GAZE  dir={gdir:6s}  viol={int(bool(gviol))}  dur={gdur:.1f}s",
            RED if gviol else WHITE)
        put(f"  h_dev={fmt(hx)} thr={GAZE_H:+.2f}   v_dev={fmt(hy)} thr={GAZE_V:+.2f}",
            GREY)
        put(f"  gated={'open ' if head_forward else 'CLOSED'} (head must be forward)",
            GREEN if head_forward else AMBER)

        # Head pose
        hpdir = hp.get("direction", "-")
        hpviol = hp.get("is_violation", False)
        hpdur = hp.get("violation_duration", 0.0)
        put(f"HEAD  dir={hpdir:10s} viol={int(bool(hpviol))} dur={hpdur:.1f}s",
            RED if hpviol else WHITE)
        put(f"  yaw_dev={fmt(yaw_dev)} thr={YAW_THRESHOLD:+.1f}  pitch_dev={fmt(pitch_dev)} thr={PITCH_THRESHOLD:+.1f}",
            GREY)

        # Lip
        mar = lip.get("mar")
        lviol = lip.get("is_violation", False)
        ldur = lip.get("violation_duration", 0.0)
        put(f"LIPS  MAR={fmt(mar)}  thr={MAR_THRESHOLD:+.2f}  viol={int(bool(lviol))} dur={ldur:.1f}s",
            RED if lviol else WHITE)

        # Objects summary
        det_names = [d["class_name"] for d in objs.get("detections", [])]
        put(f"OBJS  persons={objs.get('person_count', 0)}  "
            f"phone={'Y' if objs.get('has_phone') else 'N'}  "
            f"book={'Y' if objs.get('has_book') else 'N'}",
            RED if (objs.get("has_phone") or objs.get("has_book")) else WHITE)
        if det_names:
            put(f"  seen: {', '.join(det_names[:6])}", GREY)

        # Face presence
        put(f"FACE  detected={face_detected}  count={face_count}",
            RED if face_count > 1 or not face_detected else WHITE)

        # Last violations
        put("")
        put("RECENT VIOLATIONS (latest first):", CYAN)
        if not recent_violations:
            put("  (none yet)", GREY)
        else:
            for (t, vt, conf, meta) in recent_violations:
                age = now - t
                extra = ""
                if meta:
                    if "direction" in meta:
                        extra = f" [{meta['direction']}]"
                    elif "class" in meta:
                        extra = f" [{meta['class']}]"
                colour = VIOL_COLOURS.get(vt, WHITE)
                put(f"  {age:5.1f}s ago  {vt}{extra}  conf={conf:.2f}", colour)

        # ---------- BOTTOM TIMELINE STRIP ----------
        strip_h = 28
        strip_y = h - strip_h
        cv2.rectangle(frame, (0, strip_y), (w, h), (25, 25, 30), -1)
        cv2.putText(frame, "timeline (last 60s)", (8, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, GREY, 1, cv2.LINE_AA)
        window = 60.0
        for (t, vt) in timeline:
            age = now - t
            if age > window:
                continue
            x = int(w - (age / window) * w)
            colour = VIOL_COLOURS.get(vt, WHITE)
            cv2.rectangle(frame, (x - 2, strip_y + 3), (x + 2, h - 3), colour, -1)

        # ---------- SHOW ----------
        cv2.imshow("ProctorVision Full Pipeline — press q to quit", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

        # Terminal heartbeat every 1s
        if now - last_print > 1.0:
            last_print = now
            print(
                f"t={now-start_time:5.1f}s  cal={cal_state:11s}  risk={risk:3d}  "
                f"gaze(h={fmt(hx)} v={fmt(hy)} viol={int(bool(gviol))})  "
                f"head(y={fmt(yaw_dev)} p={fmt(pitch_dev)} viol={int(bool(hpviol))})  "
                f"mar={fmt(mar)} lip_viol={int(bool(lviol))}  "
                f"faces={face_count}  persons={objs.get('person_count', 0)}"
            )

    cap.release()
    cv2.destroyAllWindows()
    summary = pipeline.end_session()

    # ---------- FINAL SUMMARY ----------
    print()
    print("=" * 68)
    print("  FULL PIPELINE DIAGNOSTIC — SUMMARY")
    print("=" * 68)
    print(f"  session duration:   {summary.get('duration_seconds', 0):.1f}s")
    print(f"  final risk score:   {summary.get('risk_score', 0)}/100")
    print(f"  total violations:   {summary.get('total_violations', 0)}")
    print(f"  violation counts:   {summary.get('violation_counts', {})}")
    print()
    print("  Max signals observed (head-forward only for gaze):")
    print(f"    gaze_h     = {max_signals['gaze_h']:.3f}  (thr {GAZE_H})")
    print(f"    gaze_v     = {max_signals['gaze_v']:.3f}  (thr {GAZE_V})")
    print(f"    yaw_dev    = {max_signals['yaw_dev']:.2f}°  (thr {YAW_THRESHOLD})")
    print(f"    pitch_dev  = {max_signals['pitch_dev']:.2f}°  (thr {PITCH_THRESHOLD})")
    print(f"    MAR max    = {max_signals['mar']:.3f}  (thr {MAR_THRESHOLD})")
    print()
    all_types = [
        "gaze_deviation", "head_pose", "lip_movement",
        "phone_detected", "book_detected", "multiple_faces",
        "face_absent", "earpiece_detected",
    ]
    print("  Detectors that fired at least once:")
    for t in all_types:
        hit = "YES" if t in fired_types else " no"
        print(f"    [{hit}]  {t}")
    print("=" * 68)


if __name__ == "__main__":
    main()
