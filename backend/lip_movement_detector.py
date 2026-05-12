"""
ProctorVision — Lip Movement Detector Module
===============================================
Detects if the candidate is speaking using Mouth Aspect Ratio (MAR).

Technical approach:
- Computes MAR from MediaPipe FaceLandmarker mouth landmarks
- MAR = (vertical mouth opening) / (horizontal mouth width)
- MAR > 0.4 sustained for > 1.5 seconds = talking violation
- Duration threshold distinguishes speech from natural mouth movements
  (swallowing, small adjustments, yawning)

Mouth landmarks used (FaceLandmarker indices):
    - Upper lip top:     13
    - Lower lip bottom:  14
    - Left mouth corner: 78
    - Right mouth corner: 308
    - Upper lip inner:   82  (for vertical distance)
    - Lower lip inner:   87  (for vertical distance)

Note: Uses landmark data from MediaPipe Tasks API (FaceLandmarker).
"""

import time
import numpy as np

# MediaPipe FaceLandmarker mouth landmark indices
# Outer mouth corners (horizontal width)
MOUTH_LEFT = 78
MOUTH_RIGHT = 308

# Vertical mouth opening (inner lip edges for more accurate MAR)
UPPER_LIP_TOP = 13
LOWER_LIP_BOTTOM = 14
UPPER_LIP_INNER = 82
LOWER_LIP_INNER = 87

# Additional vertical reference points for more robust MAR
UPPER_LIP_MID_1 = 81
LOWER_LIP_MID_1 = 178
UPPER_LIP_MID_2 = 311
LOWER_LIP_MID_2 = 402

# MAR threshold — above this means mouth is significantly open (likely talking)
# Real-world MAR during speech is typically 0.25-0.50, resting is 0.05-0.15
MAR_THRESHOLD = 0.17

# Minimum sustained duration before logging a talking violation (seconds)
SUSTAINED_DURATION = 4.0

# Cooldown between violations of the same type (seconds)
VIOLATION_COOLDOWN = 3.0

# Grace period — brief dips below threshold during speech don't reset the timer
# (MAR naturally fluctuates during talking)
SPEAKING_GRACE_PERIOD = 0.5


class LipMovementDetector:
    """
    Detects lip movement / talking using Mouth Aspect Ratio (MAR).

    MAR is the ratio of vertical mouth opening to horizontal mouth width.
    A sustained high MAR indicates the candidate is speaking — reading
    answers aloud or talking to someone off-screen.
    """

    def __init__(self):
        self.speaking_start_time = None    # When sustained mouth opening began
        self.last_violation_time = 0.0     # For cooldown tracking
        self.last_speaking_time = None     # Last time MAR was above threshold
        self.mar_history = []              # Recent MAR values for smoothing
        self.history_size = 10             # Number of frames to average (more = smoother)

    def _compute_mar(self, landmarks, image_width, image_height):
        """
        Compute the Mouth Aspect Ratio (MAR).

        MAR = average(vertical distances) / horizontal distance

        Uses multiple vertical measurement points for robustness.

        Args:
            landmarks: List of NormalizedLandmark from FaceLandmarker result.
            image_width: Width of the input frame.
            image_height: Height of the input frame.

        Returns:
            float: Mouth Aspect Ratio value.
        """
        def _get_point(idx):
            lm = landmarks[idx]
            return np.array([lm.x * image_width, lm.y * image_height])

        # Horizontal mouth width (corner to corner)
        left_corner = _get_point(MOUTH_LEFT)
        right_corner = _get_point(MOUTH_RIGHT)
        horizontal_dist = np.linalg.norm(right_corner - left_corner)

        # Vertical mouth opening — average of multiple measurement points
        # Centre vertical
        upper_inner = _get_point(UPPER_LIP_INNER)
        lower_inner = _get_point(LOWER_LIP_INNER)
        vertical_centre = np.linalg.norm(lower_inner - upper_inner)

        # Outer vertical (top to bottom)
        upper_top = _get_point(UPPER_LIP_TOP)
        lower_bottom = _get_point(LOWER_LIP_BOTTOM)
        vertical_outer = np.linalg.norm(lower_bottom - upper_top)

        # Side verticals for more robust measurement
        upper_mid1 = _get_point(UPPER_LIP_MID_1)
        lower_mid1 = _get_point(LOWER_LIP_MID_1)
        vertical_side1 = np.linalg.norm(lower_mid1 - upper_mid1)

        upper_mid2 = _get_point(UPPER_LIP_MID_2)
        lower_mid2 = _get_point(LOWER_LIP_MID_2)
        vertical_side2 = np.linalg.norm(lower_mid2 - upper_mid2)

        # Average vertical distance
        avg_vertical = (vertical_centre + vertical_outer + vertical_side1 + vertical_side2) / 4.0

        # Avoid division by zero
        if horizontal_dist < 1e-6:
            return 0.0

        mar = avg_vertical / horizontal_dist
        return mar

    def _smooth_mar(self, mar_value):
        """
        Apply simple moving average to MAR values for noise reduction.

        Returns smoothed MAR value.
        """
        self.mar_history.append(mar_value)
        if len(self.mar_history) > self.history_size:
            self.mar_history.pop(0)

        return np.mean(self.mar_history)

    def detect(self, landmarks, image_width, image_height):
        """
        Detect lip movement / talking from face landmarks.

        Args:
            landmarks: List of NormalizedLandmark from FaceLandmarker result.
            image_width: Width of the input frame.
            image_height: Height of the input frame.

        Returns:
            dict with keys:
                - 'mar': float — current Mouth Aspect Ratio (smoothed)
                - 'raw_mar': float — unsmoothed MAR value
                - 'is_speaking': bool — True if MAR exceeds threshold
                - 'is_violation': bool — True if sustained speaking detected
                - 'violation_duration': float — seconds of sustained speaking
                - 'confidence': float — confidence of detection (0-1)
        """
        # Compute raw MAR
        raw_mar = self._compute_mar(landmarks, image_width, image_height)

        # Apply smoothing
        smoothed_mar = self._smooth_mar(raw_mar)

        # Check if mouth is open beyond threshold
        is_speaking = smoothed_mar > MAR_THRESHOLD

        # Track sustained speaking for violation detection
        is_violation, violation_duration = self._check_sustained_speaking(is_speaking)

        # Confidence based on how far MAR exceeds threshold
        if is_speaking:
            confidence = min(1.0, (smoothed_mar - MAR_THRESHOLD) / 0.3)
        else:
            confidence = 0.0

        return {
            "mar": smoothed_mar,
            "raw_mar": raw_mar,
            "is_speaking": is_speaking,
            "is_violation": is_violation,
            "violation_duration": violation_duration,
            "confidence": confidence,
        }

    def _check_sustained_speaking(self, is_speaking):
        """
        Check if the candidate has been speaking for longer than the threshold.

        Uses a grace period to handle natural MAR fluctuations during speech.
        Brief dips below threshold (< 0.5s) don't reset the timer.

        Returns (is_violation: bool, duration: float)
        """
        current_time = time.time()

        if is_speaking:
            self.last_speaking_time = current_time

            # Start tracking if not already
            if self.speaking_start_time is None:
                self.speaking_start_time = current_time
                return False, 0.0
        else:
            # MAR dipped below threshold — check grace period
            if self.last_speaking_time is not None:
                silence_duration = current_time - self.last_speaking_time
                if silence_duration > SPEAKING_GRACE_PERIOD:
                    # Genuine silence — reset timer
                    self.speaking_start_time = None
                    self.last_speaking_time = None
                    return False, 0.0
                # Within grace period — keep tracking
            else:
                return False, 0.0

        if self.speaking_start_time is None:
            return False, 0.0

        duration = current_time - self.speaking_start_time

        if duration >= SUSTAINED_DURATION:
            # Check cooldown
            if current_time - self.last_violation_time >= VIOLATION_COOLDOWN:
                self.last_violation_time = current_time
                return True, duration
            else:
                # In cooldown period — still tracking but not re-firing
                return False, duration

        return False, duration

    def get_mouth_landmarks_2d(self, landmarks, image_width, image_height):
        """
        Get 2D pixel positions of mouth landmarks for visualisation.

        Returns dict with named landmark positions.
        """
        def _get_point(idx):
            lm = landmarks[idx]
            return (int(lm.x * image_width), int(lm.y * image_height))

        return {
            "left_corner": _get_point(MOUTH_LEFT),
            "right_corner": _get_point(MOUTH_RIGHT),
            "upper_top": _get_point(UPPER_LIP_TOP),
            "lower_bottom": _get_point(LOWER_LIP_BOTTOM),
            "upper_inner": _get_point(UPPER_LIP_INNER),
            "lower_inner": _get_point(LOWER_LIP_INNER),
        }

    def reset(self):
        """Reset the detector state for a new session."""
        self.speaking_start_time = None
        self.last_violation_time = 0.0
        self.last_speaking_time = None
        self.mar_history = []
