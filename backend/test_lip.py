"""
ProctorVision — Standalone Lip Movement Detector Test
=======================================================
Run this script to test lip/talking detection with your webcam.

Usage:
    python test_lip.py

Controls:
    - Press 'q' to quit

The script will display:
    - Live webcam feed with mouth landmarks drawn
    - MAR (Mouth Aspect Ratio) value — live bar indicator
    - Speaking status (SPEAKING / SILENT)
    - Violation status when sustained speaking detected
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import os
from lip_movement_detector import LipMovementDetector, MAR_THRESHOLD

# --- MediaPipe Tasks API setup ---
BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_landmarker.task")

# Colours
COLOUR_GREEN = (0, 255, 0)
COLOUR_RED = (0, 0, 255)
COLOUR_YELLOW = (0, 255, 255)
COLOUR_CYAN = (255, 255, 0)
COLOUR_WHITE = (255, 255, 255)
COLOUR_MAGENTA = (255, 0, 255)
COLOUR_BG = (30, 30, 30)


def draw_mouth_landmarks(frame, lip_detector, landmarks, w, h):
    """Draw mouth reference landmarks and connecting lines."""
    pts = lip_detector.get_mouth_landmarks_2d(landmarks, w, h)

    # Draw landmark points
    for name, point in pts.items():
        colour = COLOUR_MAGENTA if "inner" in name else COLOUR_CYAN
        cv2.circle(frame, point, 3, colour, -1)

    # Draw mouth outline
    cv2.line(frame, pts["left_corner"], pts["upper_top"], COLOUR_YELLOW, 1)
    cv2.line(frame, pts["upper_top"], pts["right_corner"], COLOUR_YELLOW, 1)
    cv2.line(frame, pts["right_corner"], pts["lower_bottom"], COLOUR_YELLOW, 1)
    cv2.line(frame, pts["lower_bottom"], pts["left_corner"], COLOUR_YELLOW, 1)

    # Draw vertical measurement line (inner lips)
    cv2.line(frame, pts["upper_inner"], pts["lower_inner"], COLOUR_GREEN, 2)


def draw_mar_bar(frame, mar_value, x, y, bar_width=200, bar_height=20):
    """Draw a visual bar showing the current MAR value."""
    # Background
    cv2.rectangle(frame, (x, y), (x + bar_width, y + bar_height), (50, 50, 50), -1)

    # MAR fill — clamped to [0, 1] for display
    fill_width = int(min(1.0, mar_value) * bar_width)
    colour = COLOUR_RED if mar_value > MAR_THRESHOLD else COLOUR_GREEN
    cv2.rectangle(frame, (x, y), (x + fill_width, y + bar_height), colour, -1)

    # Threshold marker
    threshold_x = x + int(MAR_THRESHOLD * bar_width)
    cv2.line(frame, (threshold_x, y - 3), (threshold_x, y + bar_height + 3), COLOUR_WHITE, 2)

    # Border
    cv2.rectangle(frame, (x, y), (x + bar_width, y + bar_height), COLOUR_WHITE, 1)


def draw_info_panel(frame, lip_result):
    """Draw the information overlay panel on the frame."""
    h, w = frame.shape[:2]

    # Semi-transparent background
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (400, 200), COLOUR_BG, -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    y_offset = 35

    cv2.putText(frame, "ProctorVision - Lip Movement Test", (20, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOUR_CYAN, 1)
    y_offset += 30

    if lip_result:
        # MAR values
        cv2.putText(frame, f"MAR: {lip_result['mar']:.3f} (raw: {lip_result['raw_mar']:.3f})",
                    (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_WHITE, 1)
        y_offset += 22

        # Threshold indicator
        cv2.putText(frame, f"Threshold: {MAR_THRESHOLD}", (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOUR_YELLOW, 1)
        y_offset += 22

        # MAR bar
        draw_mar_bar(frame, lip_result["mar"], 20, y_offset)
        y_offset += 35

        # Speaking status
        if lip_result["is_speaking"]:
            cv2.putText(frame, "Status: SPEAKING", (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOUR_RED, 2)
        else:
            cv2.putText(frame, "Status: SILENT", (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOUR_GREEN, 2)
        y_offset += 30

        # Violation
        if lip_result["is_violation"]:
            dur = lip_result["violation_duration"]
            cv2.putText(frame, f"!! TALKING VIOLATION ({dur:.1f}s) !!", (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOUR_RED, 2)
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), COLOUR_RED, 4)
        elif lip_result["violation_duration"] > 0:
            dur = lip_result["violation_duration"]
            cv2.putText(frame, f"Speaking for: {dur:.1f}s", (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_YELLOW, 1)

    # Controls
    cv2.putText(frame, "[Q] Quit", (20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_WHITE, 1)


def main():
    print("=" * 60)
    print("  ProctorVision — Lip Movement Detector Standalone Test")
    print("=" * 60)
    print()

    if not os.path.exists(MODEL_PATH):
        print(f"  ERROR: Model file not found at: {MODEL_PATH}")
        return

    print("  Try speaking to trigger detection!")
    print("  Controls: [Q] Quit")
    print()

    lip_detector = LipMovementDetector()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    with FaceLandmarker.create_from_options(options) as landmarker:
        print("  FaceLandmarker initialised. Camera opened.")
        fps_time = time.time()
        frame_count = 0
        fps = 0
        start_ms = int(time.time() * 1000)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            timestamp_ms = int(time.time() * 1000) - start_ms
            frame_count += 1

            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            lip_result = None

            if result.face_landmarks and len(result.face_landmarks) > 0:
                landmarks = result.face_landmarks[0]
                draw_mouth_landmarks(frame, lip_detector, landmarks, w, h)
                lip_result = lip_detector.detect(landmarks, w, h)
            else:
                cv2.putText(frame, "No face detected", (w // 2 - 100, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            draw_info_panel(frame, lip_result)

            # FPS
            if frame_count % 30 == 0:
                fps = 30 / (time.time() - fps_time + 1e-6)
                fps_time = time.time()
            cv2.putText(frame, f"FPS: {fps:.0f}", (w - 120, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOUR_GREEN, 1)

            cv2.imshow("ProctorVision - Lip Movement Test", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()
    print("\n  Test complete. Camera released.")


if __name__ == "__main__":
    main()
