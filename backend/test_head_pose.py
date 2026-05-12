"""
ProctorVision — Standalone Head Pose Estimator Test
=====================================================
Run this script to test head pose detection with your webcam.

Uses MediaPipe Tasks API (FaceLandmarker) + OpenCV solvePnP.

Usage:
    python test_head_pose.py

Controls:
    - Press 'c' to capture calibration baseline (look straight at screen first!)
    - Press 'r' to reset calibration
    - Press 'q' to quit

The script will display:
    - Live webcam feed with pose reference landmarks drawn
    - 3D axis overlay on nose showing head orientation
    - Euler angles (pitch, yaw, roll) in degrees
    - Head direction classification
    - Violation status
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import os
from head_pose_estimator import HeadPoseEstimator, POSE_LANDMARK_INDICES

# --- MediaPipe Tasks API setup ---
BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_landmarker.task")

# Colours
COLOUR_GREEN = (0, 255, 0)
COLOUR_RED = (0, 0, 255)
COLOUR_BLUE = (255, 0, 0)
COLOUR_YELLOW = (0, 255, 255)
COLOUR_CYAN = (255, 255, 0)
COLOUR_WHITE = (255, 255, 255)
COLOUR_BG = (30, 30, 30)


def draw_pose_landmarks(frame, landmarks, w, h):
    """Draw the 6 pose reference landmarks on the frame."""
    for idx in POSE_LANDMARK_INDICES:
        lm = landmarks[idx]
        x, y = int(lm.x * w), int(lm.y * h)
        cv2.circle(frame, (x, y), 4, COLOUR_CYAN, -1)
        cv2.circle(frame, (x, y), 6, COLOUR_WHITE, 1)


def draw_3d_axis(frame, head_pose_estimator, landmarks, w, h, euler_angles):
    """
    Draw a direction line from the nose tip showing where the head is pointing.

    Uses OpenCV projectPoints for accurate 3D-to-2D projection.
    Falls back to Euler-angle-based drawing if projection unavailable.
    """
    nose = landmarks[1]  # Nose tip
    nose_x, nose_y = int(nose.x * w), int(nose.y * h)

    # Try to get the projected nose endpoint from the PnP solution
    nose_end = head_pose_estimator.get_nose_projection(w, h)

    if nose_end is not None:
        end_x, end_y = int(nose_end[0]), int(nose_end[1])
        # Draw the direction line (blue = where the nose is pointing)
        cv2.arrowedLine(frame, (nose_x, nose_y), (end_x, end_y), COLOUR_BLUE, 3, tipLength=0.15)
    else:
        # Fallback: simple direction indicator from Euler angles
        pitch, yaw, roll = euler_angles
        axis_length = 80
        end_x = int(nose_x + axis_length * np.sin(np.radians(yaw)))
        end_y = int(nose_y - axis_length * np.sin(np.radians(pitch)))
        cv2.arrowedLine(frame, (nose_x, nose_y), (end_x, end_y), COLOUR_BLUE, 3, tipLength=0.15)

    # Draw nose centre point
    cv2.circle(frame, (nose_x, nose_y), 5, COLOUR_GREEN, -1)


def draw_info_panel(frame, pose_result, is_calibrated, calibration_frames=0):
    """Draw the information overlay panel on the frame."""
    h, w = frame.shape[:2]

    # Semi-transparent background
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (420, 230), COLOUR_BG, -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    y_offset = 35

    cv2.putText(frame, "ProctorVision - Head Pose Test", (20, y_offset),
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

    if pose_result and pose_result["direction"] != "unknown":
        angles = pose_result["euler_angles"]
        dev = pose_result["deviation"]

        # Euler angles
        cv2.putText(frame, f"Pitch: {angles[0]:+6.1f}  Yaw: {angles[1]:+6.1f}  Roll: {angles[2]:+6.1f}",
                    (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_WHITE, 1)
        y_offset += 22

        # Deviation from baseline
        cv2.putText(frame, f"Dev P: {dev[0]:+6.1f}  Y: {dev[1]:+6.1f}  R: {dev[2]:+6.1f}",
                    (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_WHITE, 1)
        y_offset += 25

        # Direction
        direction = pose_result["direction"]
        dir_colour = COLOUR_GREEN if direction == "forward" else COLOUR_RED
        cv2.putText(frame, f"Direction: {direction.upper()}", (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, dir_colour, 2)
        y_offset += 30

        # Violation
        if pose_result["is_violation"]:
            dur = pose_result["violation_duration"]
            cv2.putText(frame, f"!! HEAD POSE VIOLATION ({dur:.1f}s) !!", (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOUR_RED, 2)
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), COLOUR_RED, 4)
        elif pose_result["violation_duration"] > 0:
            dur = pose_result["violation_duration"]
            cv2.putText(frame, f"Deviation: {dur:.1f}s", (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOUR_YELLOW, 1)

    # Controls
    cv2.putText(frame, "[C] Calibrate  [R] Reset  [Q] Quit", (20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_WHITE, 1)


def main():
    print("=" * 60)
    print("  ProctorVision — Head Pose Estimator Standalone Test")
    print("=" * 60)
    print()

    if not os.path.exists(MODEL_PATH):
        print(f"  ERROR: Model file not found at: {MODEL_PATH}")
        return

    print("  Controls:")
    print("    [C] - Calibrate (look straight at screen first!)")
    print("    [R] - Reset calibration")
    print("    [Q] - Quit")
    print()

    head_pose = HeadPoseEstimator()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Calibration state
    is_calibrated = False
    calibration_angles = []
    calibrating = False
    calibration_start_time = 0
    CALIBRATION_DURATION = 3.0

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

            pose_result = None

            if result.face_landmarks and len(result.face_landmarks) > 0:
                landmarks = result.face_landmarks[0]

                # Draw pose reference landmarks
                draw_pose_landmarks(frame, landmarks, w, h)

                # Run head pose estimation
                pose_result = head_pose.estimate(landmarks, w, h)

                if pose_result["direction"] != "unknown":
                    # Draw 3D axis on nose
                    draw_3d_axis(frame, head_pose, landmarks, w, h, pose_result["euler_angles"])

                    # Handle calibration
                    if calibrating:
                        elapsed = time.time() - calibration_start_time
                        if elapsed < CALIBRATION_DURATION:
                            calibration_angles.append(pose_result["euler_angles"].copy())
                        else:
                            baseline = np.mean(calibration_angles, axis=0)
                            head_pose.set_baseline(baseline)
                            is_calibrated = True
                            calibrating = False
                            print(f"  Calibration complete! Baseline: P={baseline[0]:.1f} Y={baseline[1]:.1f} R={baseline[2]:.1f}")
                            print(f"  Collected {len(calibration_angles)} frames.")
            else:
                cv2.putText(frame, "No face detected", (w // 2 - 100, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOUR_RED, 2)

            draw_info_panel(
                frame, pose_result, is_calibrated,
                calibration_frames=len(calibration_angles) if calibrating else 0
            )

            # FPS
            if frame_count % 30 == 0:
                fps = 30 / (time.time() - fps_time + 1e-6)
                fps_time = time.time()
            cv2.putText(frame, f"FPS: {fps:.0f}", (w - 120, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOUR_GREEN, 1)

            cv2.imshow("ProctorVision - Head Pose Test", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("c"):
                print("  Starting calibration... Look straight at the screen!")
                calibrating = True
                calibration_angles = []
                calibration_start_time = time.time()
                is_calibrated = False
                head_pose.reset()
            elif key == ord("r"):
                print("  Calibration reset.")
                head_pose.reset()
                is_calibrated = False
                calibrating = False
                calibration_angles = []

    cap.release()
    cv2.destroyAllWindows()
    print("\n  Test complete. Camera released.")


if __name__ == "__main__":
    main()
