"""
ProctorVision — Standalone Gaze Estimator Test
================================================
Run this script to test gaze tracking with your webcam.

Uses MediaPipe Tasks API (FaceLandmarker) — compatible with mediapipe 0.10.35+.

Usage:
    python test_gaze.py

Controls:
    - Press 'c' to capture calibration baseline (look straight at screen first!)
    - Press 'r' to reset calibration
    - Press 'q' to quit

The script will display:
    - Live webcam feed with iris landmarks drawn
    - Current gaze direction (centre/left/right/up/down)
    - Deviation values from baseline
    - Violation status (when sustained deviation detected)
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import os
from gaze_estimator import (
    GazeEstimator,
    LEFT_IRIS_INDICES, RIGHT_IRIS_INDICES,
    LEFT_EYE_INNER, LEFT_EYE_OUTER, LEFT_EYE_TOP, LEFT_EYE_BOTTOM,
    RIGHT_EYE_INNER, RIGHT_EYE_OUTER, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM,
)

# --- MediaPipe Tasks API setup ---
BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

# Path to the face landmarker model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_landmarker.task")

# Colour scheme for the overlay
COLOUR_GREEN = (0, 255, 0)
COLOUR_RED = (0, 0, 255)
COLOUR_YELLOW = (0, 255, 255)
COLOUR_CYAN = (255, 255, 0)
COLOUR_WHITE = (255, 255, 255)
COLOUR_BG = (30, 30, 30)


def draw_iris_landmarks(frame, landmarks, w, h):
    """Draw iris centre points on the frame."""
    for idx in LEFT_IRIS_INDICES + RIGHT_IRIS_INDICES:
        lm = landmarks[idx]
        x, y = int(lm.x * w), int(lm.y * h)
        cv2.circle(frame, (x, y), 2, COLOUR_CYAN, -1)

    # Draw larger circle on iris centres (468 = left iris centre, 473 = right iris centre)
    for idx in [468, 473]:
        lm = landmarks[idx]
        x, y = int(lm.x * w), int(lm.y * h)
        cv2.circle(frame, (x, y), 4, COLOUR_GREEN, 2)


def draw_eye_boxes(frame, landmarks, w, h):
    """Draw bounding boxes around each eye for reference."""
    for inner, outer, top, bottom in [
        (LEFT_EYE_INNER, LEFT_EYE_OUTER, LEFT_EYE_TOP, LEFT_EYE_BOTTOM),
        (RIGHT_EYE_INNER, RIGHT_EYE_OUTER, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM),
    ]:
        pts = []
        for idx in [inner, outer, top, bottom]:
            lm = landmarks[idx]
            pts.append((int(lm.x * w), int(lm.y * h)))

        x_coords = [p[0] for p in pts]
        y_coords = [p[1] for p in pts]
        cv2.rectangle(
            frame,
            (min(x_coords) - 5, min(y_coords) - 5),
            (max(x_coords) + 5, max(y_coords) + 5),
            COLOUR_YELLOW, 1,
        )


def draw_info_panel(frame, gaze_result, is_calibrated, calibration_frames=0):
    """Draw the information overlay panel on the frame."""
    h, w = frame.shape[:2]

    # Semi-transparent background for info panel
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (400, 200), COLOUR_BG, -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    y_offset = 35

    # Title
    cv2.putText(frame, "ProctorVision - Gaze Test", (20, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOUR_CYAN, 1)
    y_offset += 30

    # Calibration status
    if is_calibrated:
        cv2.putText(frame, "Calibrated: YES", (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOUR_GREEN, 1)
    else:
        text = f"Calibrating... ({calibration_frames} frames)" if calibration_frames > 0 else "Press 'c' to calibrate"
        cv2.putText(frame, text, (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOUR_YELLOW, 1)
    y_offset += 25

    if gaze_result:
        # Gaze direction
        direction = gaze_result["direction"]
        dir_colour = COLOUR_GREEN if direction == "centre" else COLOUR_RED
        cv2.putText(frame, f"Direction: {direction.upper()}", (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, dir_colour, 2)
        y_offset += 25

        # Deviation values
        dev = gaze_result["deviation"]
        cv2.putText(frame, f"H-dev: {dev[0]:.3f}  V-dev: {dev[1]:.3f}", (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_WHITE, 1)
        y_offset += 25

        # Raw gaze vector
        gaze = gaze_result["gaze_vector"]
        cv2.putText(frame, f"Gaze: [{gaze[0]:.3f}, {gaze[1]:.3f}]", (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_WHITE, 1)
        y_offset += 25

        # Violation status
        if gaze_result["is_violation"]:
            dur = gaze_result["violation_duration"]
            cv2.putText(frame, f"!! VIOLATION ({dur:.1f}s) !!", (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOUR_RED, 2)

            # Big red border around the frame
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), COLOUR_RED, 4)
        elif gaze_result["violation_duration"] > 0:
            dur = gaze_result["violation_duration"]
            cv2.putText(frame, f"Deviation: {dur:.1f}s", (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOUR_YELLOW, 1)

    # Controls hint at the bottom
    cv2.putText(frame, "[C] Calibrate  [R] Reset  [Q] Quit", (20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_WHITE, 1)


def main():
    print("=" * 60)
    print("  ProctorVision — Gaze Estimator Standalone Test")
    print("=" * 60)
    print()

    # Check model file exists
    if not os.path.exists(MODEL_PATH):
        print(f"  ERROR: Model file not found at: {MODEL_PATH}")
        print("  Download it with:")
        print('  Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task" -OutFile "models\\face_landmarker.task"')
        return

    print("  Controls:")
    print("    [C] - Calibrate (look straight at screen first!)")
    print("    [R] - Reset calibration")
    print("    [Q] - Quit")
    print()

    gaze = GazeEstimator()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERROR: Could not open webcam. Check camera permissions.")
        return

    # Set camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Calibration state
    is_calibrated = False
    calibration_vectors = []
    calibrating = False
    calibration_start_time = 0
    CALIBRATION_DURATION = 3.0  # Seconds to collect calibration data

    # Create FaceLandmarker with VIDEO running mode
    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
    )

    with FaceLandmarker.create_from_options(options) as landmarker:
        print("  FaceLandmarker initialised. Camera opened.")
        print("  Waiting for face detection...")

        fps_time = time.time()
        frame_count = 0
        start_ms = int(time.time() * 1000)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("ERROR: Failed to read frame from webcam.")
                break

            # Flip horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Create MediaPipe Image from numpy array
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Compute timestamp in milliseconds (must be monotonically increasing)
            timestamp_ms = int(time.time() * 1000) - start_ms
            frame_count += 1

            # Run face landmark detection
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            gaze_result = None

            if result.face_landmarks and len(result.face_landmarks) > 0:
                # Get landmarks for the first detected face
                landmarks = result.face_landmarks[0]

                # Check if we have iris landmarks (need 478 landmarks total)
                if len(landmarks) >= 478:
                    # Draw iris landmarks and eye boxes
                    draw_iris_landmarks(frame, landmarks, w, h)
                    draw_eye_boxes(frame, landmarks, w, h)

                    # Run gaze estimation
                    gaze_result = gaze.estimate(landmarks, w, h)

                    # Handle calibration collection
                    if calibrating:
                        elapsed = time.time() - calibration_start_time
                        if elapsed < CALIBRATION_DURATION:
                            calibration_vectors.append(gaze_result["gaze_vector"].copy())
                        else:
                            # Compute baseline as average of collected vectors
                            baseline = np.mean(calibration_vectors, axis=0)
                            gaze.set_baseline(baseline)
                            is_calibrated = True
                            calibrating = False
                            print(f"  Calibration complete! Baseline: [{baseline[0]:.4f}, {baseline[1]:.4f}]")
                            print(f"  Collected {len(calibration_vectors)} frames.")
                else:
                    cv2.putText(frame, f"Landmarks: {len(landmarks)} (need 478 for iris)", (20, h // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOUR_YELLOW, 1)
            else:
                # No face detected
                cv2.putText(frame, "No face detected", (w // 2 - 100, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOUR_RED, 2)

            # Draw info panel
            draw_info_panel(
                frame, gaze_result, is_calibrated,
                calibration_frames=len(calibration_vectors) if calibrating else 0
            )

            # FPS counter
            if frame_count % 30 == 0:
                fps = 30 / (time.time() - fps_time + 1e-6)
                fps_time = time.time()
            if frame_count > 30:
                cv2.putText(frame, f"FPS: {fps:.0f}", (w - 120, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOUR_GREEN, 1)

            cv2.imshow("ProctorVision - Gaze Test", frame)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("c"):
                # Start calibration
                print("  Starting calibration... Look straight at the screen!")
                calibrating = True
                calibration_vectors = []
                calibration_start_time = time.time()
                is_calibrated = False
                gaze.reset()

            elif key == ord("r"):
                # Reset calibration
                print("  Calibration reset.")
                gaze.reset()
                is_calibrated = False
                calibrating = False
                calibration_vectors = []

    cap.release()
    cv2.destroyAllWindows()
    print("\n  Test complete. Camera released.")


if __name__ == "__main__":
    main()
