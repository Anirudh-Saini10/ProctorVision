"""
ProctorVision — Gaze Estimator Module
======================================
Detects where the candidate is looking using MediaPipe FaceLandmarker iris landmarks.

Technical approach:
- MediaPipe FaceLandmarker (Tasks API) returns 478 3D landmarks per face
- Iris landmarks (468-477) provide pupil centre coordinates
- Gaze vector = offset of iris centre from eye bounding box centre, normalised
- Calibration baseline allows personalised thresholds (no hardcoded universal values)

Thresholds (relative to calibrated baseline):
- Left/right deviation: iris centre offset > 0.35 normalised units
- Up/down deviation: vertical iris offset > 0.30 normalised units
- Sustained deviation > 2 seconds: violation logged

Note: Uses MediaPipe Tasks API (0.10.35+), NOT the legacy mp.solutions API.
"""

import time
import numpy as np

# MediaPipe FaceLandmarker landmark indices for iris tracking
# Left iris: 468-472 (468 = centre)
# Right iris: 473-477 (473 = centre)
LEFT_IRIS_CENTER = 468
RIGHT_IRIS_CENTER = 473

# Eye corner landmarks for computing gaze reference box
# Left eye corners (from subject's perspective)
LEFT_EYE_INNER = 362
LEFT_EYE_OUTER = 263
LEFT_EYE_TOP = 386
LEFT_EYE_BOTTOM = 374

# Right eye corners
RIGHT_EYE_INNER = 133
RIGHT_EYE_OUTER = 33
RIGHT_EYE_TOP = 159
RIGHT_EYE_BOTTOM = 145

# All iris landmark indices for visualisation
LEFT_IRIS_INDICES = [468, 469, 470, 471, 472]
RIGHT_IRIS_INDICES = [473, 474, 475, 476, 477]

# Gaze deviation thresholds (normalised units from baseline).
#
# Offset is iris-centre displacement / eye-box dimensions, averaged across
# both eyes. Empirically, MediaPipe's iris landmarks don't travel as far as
# you'd expect with pure eye motion (model bias toward the eye centre),
# so practical eye-only deviation peaks around 0.10-0.20 horizontally and
# 0.06-0.12 vertically. Thresholds tuned to fire on a deliberate sideways
# glance (e.g. peeking at a phone) while ignoring reading micro-saccades.
#
# Gaze violations are also hard-gated in cv_pipeline.py so that they only
# count when the head is roughly forward (|yaw|<12, |pitch|<12) — that
# avoids the eye-width-denominator artifact that makes deviation values
# explode during head turns.
HORIZONTAL_THRESHOLD = 0.10
VERTICAL_THRESHOLD = 0.07

# Minimum sustained deviation duration before logging a violation (seconds).
# Shortened from 2.0 so a 1-second glance at a side phone is caught,
# while blinks (~0.2s) and saccades (~0.1s) still get filtered out.
SUSTAINED_DURATION = 1.0


class GazeEstimator:
    """
    Estimates gaze direction from MediaPipe FaceLandmarker iris landmarks.

    Uses the offset of the iris centre relative to the eye bounding box centre,
    normalised by the eye dimensions. All deviations are measured against a
    personal calibration baseline captured at session start.
    """

    def __init__(self):
        self.baseline_gaze = None  # Set during calibration
        self.deviation_start_time = None  # When sustained deviation began
        self.last_gaze_direction = "centre"

    def _extract_iris_position(self, landmarks, image_width, image_height):
        """
        Extract normalised iris position relative to eye bounding box.

        For each eye:
        1. Get iris centre (landmarks 468, 473)
        2. Get eye bounding box from corner landmarks
        3. Compute normalised offset: (iris_pos - box_centre) / box_dimensions

        Returns average of both eyes for stability.

        Args:
            landmarks: List of NormalizedLandmark from FaceLandmarker result.
                       Each has .x, .y, .z attributes (normalised 0-1).
            image_width: Width of the input frame
            image_height: Height of the input frame
        """
        def _get_point(idx):
            lm = landmarks[idx]
            return np.array([lm.x * image_width, lm.y * image_height])

        # Left eye (subject's left = our right in mirror view)
        left_iris = _get_point(LEFT_IRIS_CENTER)
        left_inner = _get_point(LEFT_EYE_INNER)
        left_outer = _get_point(LEFT_EYE_OUTER)
        left_top = _get_point(LEFT_EYE_TOP)
        left_bottom = _get_point(LEFT_EYE_BOTTOM)

        # Right eye
        right_iris = _get_point(RIGHT_IRIS_CENTER)
        right_inner = _get_point(RIGHT_EYE_INNER)
        right_outer = _get_point(RIGHT_EYE_OUTER)
        right_top = _get_point(RIGHT_EYE_TOP)
        right_bottom = _get_point(RIGHT_EYE_BOTTOM)

        # Compute normalised iris offset for each eye
        left_gaze = self._compute_normalised_offset(
            left_iris, left_inner, left_outer, left_top, left_bottom
        )
        right_gaze = self._compute_normalised_offset(
            right_iris, right_inner, right_outer, right_top, right_bottom
        )

        # Average both eyes for more stable reading
        avg_gaze = (left_gaze + right_gaze) / 2.0
        return avg_gaze

    def _compute_normalised_offset(self, iris, inner, outer, top, bottom):
        """
        Compute the normalised offset of the iris centre from the eye box centre.

        Returns [horizontal_offset, vertical_offset] where:
        - Negative horizontal = looking left (from subject's perspective)
        - Positive horizontal = looking right
        - Negative vertical = looking up
        - Positive vertical = looking down
        """
        # Eye bounding box centre
        eye_centre_x = (inner[0] + outer[0]) / 2.0
        eye_centre_y = (top[1] + bottom[1]) / 2.0

        # Eye dimensions for normalisation
        eye_width = abs(outer[0] - inner[0])
        eye_height = abs(bottom[1] - top[1])

        # Avoid division by zero
        if eye_width < 1e-6 or eye_height < 1e-6:
            return np.array([0.0, 0.0])

        # Normalised offset
        offset_x = (iris[0] - eye_centre_x) / eye_width
        offset_y = (iris[1] - eye_centre_y) / eye_height

        return np.array([offset_x, offset_y])

    def set_baseline(self, baseline_gaze_vector):
        """
        Set the calibration baseline for this session.

        Args:
            baseline_gaze_vector: np.array([horizontal, vertical]) — average gaze
                                  position when looking straight at the screen.
        """
        self.baseline_gaze = baseline_gaze_vector.copy()
        self.deviation_start_time = None
        self.last_gaze_direction = "centre"

    def estimate(self, landmarks, image_width, image_height):
        """
        Estimate gaze direction from face landmarks.

        Args:
            landmarks: List of NormalizedLandmark from FaceLandmarker result
                       (478 landmarks). Each has .x, .y, .z attributes.
            image_width: Width of the input frame
            image_height: Height of the input frame

        Returns:
            dict with keys:
                - 'gaze_vector': np.array([h_offset, v_offset]) — raw normalised gaze
                - 'direction': str — 'centre', 'left', 'right', 'up', 'down'
                - 'deviation': np.array([h_dev, v_dev]) — deviation from baseline
                - 'is_violation': bool — True if sustained deviation exceeds threshold
                - 'violation_duration': float — seconds of sustained deviation (0 if none)
                - 'confidence': float — confidence of the gaze estimate (0-1)
        """
        current_gaze = self._extract_iris_position(landmarks, image_width, image_height)

        # Compute deviation from baseline (or from zero if not calibrated)
        baseline = self.baseline_gaze if self.baseline_gaze is not None else np.array([0.0, 0.0])
        deviation = current_gaze - baseline

        # Determine gaze direction based on thresholds
        direction = self._classify_direction(deviation)

        # Track sustained deviation for violation detection
        is_violation, violation_duration = self._check_sustained_deviation(direction)

        # Confidence estimate based on deviation magnitude
        # Higher deviation from centre = higher confidence in the direction call
        dev_magnitude = np.linalg.norm(deviation)
        confidence = min(1.0, dev_magnitude / 0.5)  # Saturates at 0.5 normalised units

        self.last_gaze_direction = direction

        return {
            "gaze_vector": current_gaze,
            "direction": direction,
            "deviation": deviation,
            "is_violation": is_violation,
            "violation_duration": violation_duration,
            "confidence": confidence,
        }

    def _classify_direction(self, deviation):
        """
        Classify the gaze direction based on deviation from baseline.

        Priority: horizontal deviation checked first (more common cheating signal),
        then vertical.
        """
        h_dev, v_dev = deviation[0], deviation[1]

        # Check horizontal first (left/right looking is the primary cheating signal)
        if abs(h_dev) > HORIZONTAL_THRESHOLD:
            return "left" if h_dev < 0 else "right"

        # Check vertical
        if abs(v_dev) > VERTICAL_THRESHOLD:
            return "up" if v_dev < 0 else "down"

        return "centre"

    def _check_sustained_deviation(self, direction):
        """
        Check if the candidate has been looking away for longer than the threshold.

        Returns (is_violation: bool, duration: float)
        """
        current_time = time.time()

        if direction == "centre":
            # Reset deviation timer when looking at screen
            self.deviation_start_time = None
            return False, 0.0

        # Deviation detected — start or continue tracking
        if self.deviation_start_time is None:
            self.deviation_start_time = current_time
            return False, 0.0

        duration = current_time - self.deviation_start_time

        if duration >= SUSTAINED_DURATION:
            return True, duration

        return False, duration

    def reset(self):
        """Reset the estimator state for a new session."""
        self.baseline_gaze = None
        self.deviation_start_time = None
        self.last_gaze_direction = "centre"
