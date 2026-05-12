"""
ProctorVision — Gaze Diagnostic (LOCAL, no WebSocket).

Runs the full CVPipeline against your webcam in-process and overlays the
real numbers we threshold against:
  - iris position (gaze_vector)
  - baseline (set by 10s calibration)
  - deviation = gaze_vector - baseline
  - direction classification
  - head pose Euler angles
  - the current thresholds for reference

Goal: diagnose why eye-only motion isn't crossing the gaze threshold.

Instructions:
  1. First ~10s: SIT STILL, look straight at the camera (calibration).
  2. After "CALIBRATED" appears: try the three tests in order.
       (A) Head still, look LEFT with only your eyes for 3s — watch h_dev.
       (B) Head still, look RIGHT with only your eyes for 3s — watch h_dev.
       (C) Head still, look UP / DOWN for 3s — watch v_dev.
       (D) Then turn your HEAD left/right — watch yaw and the head_pose
           is_violation flag.
  3. Press 'q' to quit. Paste the on-screen "MAX |h_dev|" / "MAX |v_dev|"
     summary back to Cascade so we can pick the right thresholds.
"""

import time
import cv2
import numpy as np

from cv_pipeline import CVPipeline
from gaze_estimator import HORIZONTAL_THRESHOLD, VERTICAL_THRESHOLD


def fmt(v, w=6):
    if v is None:
        return " " * w
    return f"{v:+.3f}".rjust(w)


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: cannot open webcam")
        return

    pipeline = CVPipeline()
    session_id = pipeline.start_session()
    print(f"session_id={session_id}")
    print(f"thresholds: H={HORIZONTAL_THRESHOLD}  V={VERTICAL_THRESHOLD}")

    max_h_dev = 0.0
    max_v_dev = 0.0
    frame_count = 0
    last_print = 0.0

    print("Calibrating — look at camera and stay still...")

    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        frame = cv2.flip(frame, 1)
        frame_count += 1

        result = pipeline.process_frame(frame)

        gaze = result.get("gaze") or {}
        hp = result.get("head_pose") or {}
        cal = result.get("calibration") or {}
        cal_state = cal.get("state", "?")

        gv = gaze.get("gaze_vector")
        dev = gaze.get("deviation")
        direction = gaze.get("direction", "-")
        is_gaze_viol = gaze.get("is_violation", False)
        gaze_dur = gaze.get("violation_duration", 0.0)

        baseline = pipeline.gaze.baseline_gaze
        bx = baseline[0] if baseline is not None else None
        by = baseline[1] if baseline is not None else None

        gx = gv[0] if gv is not None else None
        gy = gv[1] if gv is not None else None
        hx = dev[0] if dev is not None else None
        hy = dev[1] if dev is not None else None

        # Head pose — show RAW euler for visibility, but gate on
        # baseline-relative DEVIATION (matches cv_pipeline.py).
        euler = hp.get("euler_angles") if hp else None
        hp_dev_arr = hp.get("deviation") if hp else None
        yaw = euler[1] if euler is not None else None  # [pitch, yaw, roll]
        pitch = euler[0] if euler is not None else None
        yaw_dev = hp_dev_arr[1] if hp_dev_arr is not None else None
        pitch_dev = hp_dev_arr[0] if hp_dev_arr is not None else None
        hp_dir = hp.get("direction", "-") if hp else "-"
        is_hp_viol = hp.get("is_violation", False) if hp else False

        # Only count "max" deviation while head is roughly forward
        # (relative to user's calibrated pose).
        head_forward = (
            yaw_dev is not None and pitch_dev is not None
            and abs(yaw_dev) < 15.0 and abs(pitch_dev) < 15.0
        )
        if head_forward and hx is not None:
            max_h_dev = max(max_h_dev, abs(hx))
        if head_forward and hy is not None:
            max_v_dev = max(max_v_dev, abs(hy))

        # Console summary every ~0.5s
        now = time.time()
        if now - last_print > 0.5:
            last_print = now
            print(
                f"[{cal_state:11s}] "
                f"gaze=({fmt(gx)},{fmt(gy)})  "
                f"base=({fmt(bx)},{fmt(by)})  "
                f"dev=({fmt(hx)},{fmt(hy)})  "
                f"dir={direction:6s}  "
                f"viol={int(is_gaze_viol)} dur={gaze_dur:4.1f}s  "
                f"|  yaw={fmt(yaw)} pitch={fmt(pitch)} hp_viol={int(is_hp_viol)}  "
                f"max|h|={max_h_dev:.3f} max|v|={max_v_dev:.3f}"
            )

        # On-frame overlay
        h, w = frame.shape[:2]
        line_y = 24
        def put(txt, color=(255, 255, 255)):
            nonlocal line_y
            cv2.putText(frame, txt, (10, line_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            line_y += 22

        if cal_state == "calibrating":
            put(f"CALIBRATING  {cal.get('progress', 0)*100:4.1f}%", (0, 200, 255))
        elif cal_state == "complete":
            put("CALIBRATED — try eye-only L/R/U/D for 3s", (0, 255, 0))
        else:
            put(f"state={cal_state}")

        put(f"gaze=({fmt(gx)},{fmt(gy)})")
        put(f"base=({fmt(bx)},{fmt(by)})")
        h_color = (0, 0, 255) if hx is not None and abs(hx) > HORIZONTAL_THRESHOLD else (255, 255, 255)
        v_color = (0, 0, 255) if hy is not None and abs(hy) > VERTICAL_THRESHOLD else (255, 255, 255)
        put(f"h_dev={fmt(hx)}  thr={HORIZONTAL_THRESHOLD:+.3f}", h_color)
        put(f"v_dev={fmt(hy)}  thr={VERTICAL_THRESHOLD:+.3f}", v_color)
        put(f"dir={direction}  gaze_violation={is_gaze_viol}  dur={gaze_dur:.1f}s")
        put(f"yaw={fmt(yaw)} pitch={fmt(pitch)} hp_dir={hp_dir} hp_viol={is_hp_viol}",
            (0, 0, 255) if is_hp_viol else (255, 255, 255))
        put(f"yaw_dev={fmt(yaw_dev)} pitch_dev={fmt(pitch_dev)}  (vs baseline)")
        put(f"HEAD_FWD={head_forward}  (gaze only counted when True)",
            (0, 255, 0) if head_forward else (0, 165, 255))
        put(f"MAX |h_dev|={max_h_dev:.3f}   MAX |v_dev|={max_v_dev:.3f}", (200, 200, 0))

        cv2.imshow("ProctorVision Gaze Diagnostic — press q to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    pipeline.end_session()

    print()
    print("=" * 60)
    print(f"  MAX |h_dev| observed: {max_h_dev:.3f}   threshold: {HORIZONTAL_THRESHOLD}")
    print(f"  MAX |v_dev| observed: {max_v_dev:.3f}   threshold: {VERTICAL_THRESHOLD}")
    print("=" * 60)


if __name__ == "__main__":
    main()
