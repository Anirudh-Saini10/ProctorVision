"""
ProctorVision — Calibration Module
=====================================
Captures personal gaze and head pose baselines during the first 10 seconds
of a proctoring session.

Technical approach:
- Collects N frames of gaze vectors and head pose Euler angles
- Computes the mean of each to establish the candidate's neutral position
- These baselines are then applied to GazeEstimator and HeadPoseEstimator
- All subsequent deviation measurements are relative to these personal baselines

This is the #1 accuracy feature — it eliminates false positives caused by
individual differences in eye position, face shape, camera angle, and seating.

Duration: 10 seconds (~150 frames at 15 FPS, though we may get more/fewer
depending on processing speed)
"""

import time
import numpy as np


class CalibrationManager:
    """
    Manages the calibration phase at the start of a proctoring session.

    Collects gaze vectors and head pose angles over a configurable
    duration, then computes stable baselines for personalised detection.
    """

    # Calibration states
    STATE_PENDING = "pending"
    STATE_CALIBRATING = "calibrating"
    STATE_COMPLETE = "complete"

    def __init__(self, duration=10.0, min_frames=30):
        """
        Initialize the calibration manager.

        Args:
            duration: Calibration duration in seconds (default: 10s per spec).
            min_frames: Minimum number of valid frames needed for a reliable
                       baseline. If fewer frames collected, calibration fails.
        """
        self.duration = duration
        self.min_frames = min_frames

        self.state = self.STATE_PENDING
        self.start_time = None
        self.elapsed = 0.0

        # Collected data
        self.gaze_vectors = []
        self.head_pose_angles = []
        self.face_confidences = []

        # Computed baselines (set after calibration completes)
        self.gaze_baseline = None
        self.head_pose_baseline = None
        self.avg_confidence = 0.0

    def start(self):
        """Start the calibration phase."""
        self.state = self.STATE_CALIBRATING
        self.start_time = time.time()
        self.elapsed = 0.0

        # Reset collected data
        self.gaze_vectors = []
        self.head_pose_angles = []
        self.face_confidences = []

        self.gaze_baseline = None
        self.head_pose_baseline = None

    def add_frame(self, gaze_vector=None, head_pose_angles=None, face_confidence=1.0):
        """
        Add a frame's data to the calibration buffer.

        Called once per processed frame during the calibration phase.

        Args:
            gaze_vector: np.array([h_offset, v_offset]) from GazeEstimator
            head_pose_angles: np.array([pitch, yaw, roll]) from HeadPoseEstimator
            face_confidence: Face detection confidence for this frame (0-1)
        """
        if self.state != self.STATE_CALIBRATING:
            return

        # Update elapsed time
        self.elapsed = time.time() - self.start_time

        # Only include high-confidence frames in calibration
        if face_confidence < 0.5:
            return

        if gaze_vector is not None:
            self.gaze_vectors.append(gaze_vector.copy())

        if head_pose_angles is not None:
            self.head_pose_angles.append(head_pose_angles.copy())

        self.face_confidences.append(face_confidence)

        # Check if calibration duration has elapsed
        if self.elapsed >= self.duration:
            self._compute_baselines()

    def _compute_baselines(self):
        """
        Compute the baseline values from collected calibration data.

        Uses trimmed mean (removing top/bottom 10%) for robustness
        against outlier frames (blinks, momentary glances away, etc.)
        """
        if len(self.gaze_vectors) < self.min_frames:
            # Not enough data — calibration failed, use defaults
            print(f"  WARNING: Only {len(self.gaze_vectors)} gaze frames "
                  f"collected (need {self.min_frames}). Using defaults.")
            self.gaze_baseline = np.array([0.0, 0.0])
            self.head_pose_baseline = np.array([0.0, 0.0, 0.0])
        else:
            # Compute trimmed mean for gaze (remove top/bottom 10%)
            self.gaze_baseline = self._trimmed_mean(
                np.array(self.gaze_vectors), trim_percent=0.10
            )

            # Compute trimmed mean for head pose
            if len(self.head_pose_angles) >= self.min_frames:
                self.head_pose_baseline = self._trimmed_mean(
                    np.array(self.head_pose_angles), trim_percent=0.10
                )
            else:
                self.head_pose_baseline = np.mean(
                    np.array(self.head_pose_angles), axis=0
                ) if self.head_pose_angles else np.array([0.0, 0.0, 0.0])

        # Average face confidence during calibration
        self.avg_confidence = np.mean(self.face_confidences) if self.face_confidences else 0.0

        self.state = self.STATE_COMPLETE

    @staticmethod
    def _trimmed_mean(data, trim_percent=0.10):
        """
        Compute trimmed mean, removing the top and bottom trim_percent of values.

        This is more robust than simple mean — it ignores outlier frames
        where the candidate blinked, glanced away briefly, etc.

        Args:
            data: np.array of shape (N, D) — N samples, D dimensions
            trim_percent: Fraction of samples to trim from each end

        Returns:
            np.array of shape (D,) — trimmed mean per dimension
        """
        n = len(data)
        trim_count = max(1, int(n * trim_percent))

        result = []
        for dim in range(data.shape[1]):
            col = data[:, dim]
            sorted_col = np.sort(col)
            trimmed = sorted_col[trim_count:-trim_count] if trim_count < n // 2 else sorted_col
            result.append(np.mean(trimmed))

        return np.array(result)

    def get_progress(self):
        """
        Get the current calibration progress.

        Returns:
            dict with keys:
                - 'state': str — 'pending', 'calibrating', or 'complete'
                - 'progress': float — 0.0 to 1.0 completion ratio
                - 'elapsed': float — seconds elapsed
                - 'remaining': float — seconds remaining
                - 'frames_collected': int — number of valid frames
        """
        if self.state == self.STATE_PENDING:
            return {
                "state": self.state,
                "progress": 0.0,
                "elapsed": 0.0,
                "remaining": self.duration,
                "frames_collected": 0,
            }

        elapsed = time.time() - self.start_time if self.start_time else 0.0
        progress = min(1.0, elapsed / self.duration)
        remaining = max(0.0, self.duration - elapsed)

        return {
            "state": self.state,
            "progress": progress,
            "elapsed": elapsed,
            "remaining": remaining,
            "frames_collected": len(self.gaze_vectors),
        }

    def get_baselines(self):
        """
        Get the computed baselines after calibration is complete.

        Returns:
            dict with keys:
                - 'gaze_baseline': np.array([h, v]) or None
                - 'head_pose_baseline': np.array([pitch, yaw, roll]) or None
                - 'avg_confidence': float
                - 'is_valid': bool — True if calibration completed successfully
        """
        return {
            "gaze_baseline": self.gaze_baseline,
            "head_pose_baseline": self.head_pose_baseline,
            "avg_confidence": self.avg_confidence,
            "is_valid": self.state == self.STATE_COMPLETE and self.gaze_baseline is not None,
        }

    @property
    def is_complete(self):
        """Whether calibration has finished."""
        return self.state == self.STATE_COMPLETE

    @property
    def is_calibrating(self):
        """Whether calibration is currently in progress."""
        return self.state == self.STATE_CALIBRATING

    def reset(self):
        """Reset calibration state for a new session."""
        self.state = self.STATE_PENDING
        self.start_time = None
        self.elapsed = 0.0
        self.gaze_vectors = []
        self.head_pose_angles = []
        self.face_confidences = []
        self.gaze_baseline = None
        self.head_pose_baseline = None
        self.avg_confidence = 0.0
