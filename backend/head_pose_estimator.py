"""
ProctorVision — Head Pose Estimator Module
============================================
Detects head rotation (yaw, pitch, roll) using OpenCV's solvePnP.

Technical approach:
- Uses 6 key facial landmarks from MediaPipe FaceLandmarker as 2D reference points
- Matches them against a known 3D face model (generic human face proportions)
- OpenCV solvePnP computes the rotation vector, converted to Euler angles via Rodrigues
- Temporal smoothing (exponential moving average) reduces jitter

Reference landmarks:
    - Nose tip (landmark 1)
    - Chin (landmark 152)
    - Left eye outer corner (landmark 263)
    - Right eye outer corner (landmark 33)
    - Left mouth corner (landmark 287)
    - Right mouth corner (landmark 57)

Thresholds:
    - Yaw (left/right turn) > 25 degrees: looking-away violation
    - Pitch (up/down nod) > 20 degrees: reading-notes or second-screen violation
    - Roll (head tilt) > 30 degrees: secondary signal

Note: Uses landmark data from MediaPipe Tasks API (FaceLandmarker).
"""

import time
import numpy as np
import cv2

# MediaPipe FaceLandmarker indices for head pose reference points
NOSE_TIP = 1
CHIN = 152
LEFT_EYE_OUTER = 263
RIGHT_EYE_OUTER = 33
LEFT_MOUTH_CORNER = 287
RIGHT_MOUTH_CORNER = 57

# Indices list for easy iteration
POSE_LANDMARK_INDICES = [
    NOSE_TIP, CHIN, LEFT_EYE_OUTER,
    RIGHT_EYE_OUTER, LEFT_MOUTH_CORNER, RIGHT_MOUTH_CORNER,
]

# 3D model points for a generic human face (in arbitrary units, centred at nose)
# These approximate the spatial relationships between the 6 reference points
MODEL_POINTS_3D = np.array([
    (0.0, 0.0, 0.0),            # Nose tip
    (0.0, -330.0, -65.0),       # Chin
    (-225.0, 170.0, -135.0),    # Left eye outer corner
    (225.0, 170.0, -135.0),     # Right eye outer corner
    (-150.0, -150.0, -125.0),   # Left mouth corner
    (150.0, -150.0, -125.0),    # Right mouth corner
], dtype=np.float64)

# Head pose violation thresholds (degrees)
# These are intentionally generous to avoid false positives.
# Only clearly deliberate head turning should trigger violations.
YAW_THRESHOLD = 35.0      # Left/right turn — must be a clear deliberate look away
PITCH_THRESHOLD = 30.0     # Up/down nod — generous to allow natural head movement
ROLL_THRESHOLD = 45.0      # Head tilt — very generous, tilting alone is NOT a violation

# Minimum sustained deviation duration before logging a violation (seconds)
SUSTAINED_DURATION = 2.5

# Exponential moving average factor for temporal smoothing (0-1, higher = less smoothing)
EMA_ALPHA = 0.3


class HeadPoseEstimator:
    """
    Estimates head pose (yaw, pitch, roll) from facial landmarks using PnP solver.

    Uses 6 key facial landmarks matched against a generic 3D face model.
    Euler angles are extracted via Rodrigues decomposition and smoothed
    with an exponential moving average to reduce frame-to-frame jitter.
    """

    def __init__(self):
        self.baseline_pose = None          # Set during calibration
        self.smoothed_angles = None        # EMA-smoothed Euler angles
        self.deviation_start_time = None   # When sustained deviation began
        self.last_direction = "forward"

    def _get_camera_matrix(self, image_width, image_height):
        """
        Construct an approximate camera intrinsic matrix.

        Uses focal length approximation based on image width.
        This is sufficient for relative pose estimation (we don't need
        exact camera calibration for our use case).
        """
        focal_length = image_width  # Approximate focal length
        centre_x = image_width / 2.0
        centre_y = image_height / 2.0

        camera_matrix = np.array([
            [focal_length, 0.0, centre_x],
            [0.0, focal_length, centre_y],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)

        return camera_matrix

    def _extract_2d_points(self, landmarks, image_width, image_height):
        """
        Extract 2D pixel coordinates for the 6 pose reference landmarks.

        Args:
            landmarks: List of NormalizedLandmark from FaceLandmarker result.
            image_width: Width of the input frame.
            image_height: Height of the input frame.

        Returns:
            np.array of shape (6, 2) with pixel coordinates.
        """
        points_2d = []
        for idx in POSE_LANDMARK_INDICES:
            lm = landmarks[idx]
            x = lm.x * image_width
            y = lm.y * image_height
            points_2d.append((x, y))

        return np.array(points_2d, dtype=np.float64)

    def _solve_pose(self, points_2d, camera_matrix):
        """
        Solve for head pose using PnP algorithm.

        Args:
            points_2d: 2D landmark positions in pixel space (6x2).
            camera_matrix: Camera intrinsic matrix (3x3).

        Returns:
            Euler angles (pitch, yaw, roll) in degrees, or None if solve fails.
        """
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)  # Assume no lens distortion

        success, rotation_vector, translation_vector = cv2.solvePnP(
            MODEL_POINTS_3D,
            points_2d,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            return None

        # Store rotation/translation vectors for nose projection (used in visualisation)
        self._last_rvec = rotation_vector
        self._last_tvec = translation_vector

        # Convert rotation vector to rotation matrix via Rodrigues
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)

        # Extract Euler angles using OpenCV's RQDecomp3x3
        # This is more reliable than manual decomposition and handles
        # the coordinate system correctly for face pose estimation.
        euler_angles = self._rotation_matrix_to_euler(rotation_matrix)

        return euler_angles

    @staticmethod
    def _normalize_angle(angle):
        """
        Normalize an angle to the range [-180, 180] degrees.

        This handles the coordinate system mismatch where solvePnP
        can produce angles offset by ±180° due to the z-axis convention
        difference between the 3D face model and the camera.
        """
        while angle > 180.0:
            angle -= 360.0
        while angle < -180.0:
            angle += 360.0
        return angle

    @staticmethod
    def _angular_difference(angle1, angle2):
        """
        Compute the shortest angular difference between two angles in degrees.

        Handles wrap-around correctly (e.g., 350° and 10° differ by 20°, not 340°).
        """
        diff = angle1 - angle2
        while diff > 180.0:
            diff -= 360.0
        while diff < -180.0:
            diff += 360.0
        return diff

    def _rotation_matrix_to_euler(self, rotation_matrix):
        """
        Convert a 3x3 rotation matrix to Euler angles (pitch, yaw, roll)
        using OpenCV's RQDecomp3x3 for reliable extraction.

        Returns angles in degrees, normalized to [-180, 180].
        """
        # cv2.RQDecomp3x3 returns angles in degrees directly
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_matrix)

        # Normalize all angles to [-180, 180] range
        pitch = self._normalize_angle(angles[0])
        yaw = self._normalize_angle(angles[1])
        roll = self._normalize_angle(angles[2])

        return np.array([pitch, yaw, roll])

    def get_nose_projection(self, image_width, image_height):
        """
        Get the projected 3D axis endpoint from the nose, useful for drawing
        the head direction arrow in the visualisation.

        Returns (nose_2d, nose_end_2d) tuple, or None if no pose computed yet.
        """
        if not hasattr(self, '_last_rvec') or self._last_rvec is None:
            return None

        camera_matrix = self._get_camera_matrix(image_width, image_height)
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        # Project a point 500 units in front of the nose to show direction
        nose_end_3d = np.array([(0.0, 0.0, 500.0)], dtype=np.float64)
        nose_end_2d, _ = cv2.projectPoints(
            nose_end_3d, self._last_rvec, self._last_tvec,
            camera_matrix, dist_coeffs
        )

        return nose_end_2d.reshape(-1, 2)[0]

    def _apply_smoothing(self, raw_angles):
        """
        Apply exponential moving average to smooth Euler angles.

        Reduces jitter from frame-to-frame noise in landmark detection.
        """
        if self.smoothed_angles is None:
            self.smoothed_angles = raw_angles.copy()
        else:
            self.smoothed_angles = (
                EMA_ALPHA * raw_angles + (1 - EMA_ALPHA) * self.smoothed_angles
            )
        return self.smoothed_angles.copy()

    def set_baseline(self, baseline_pose):
        """
        Set the calibration baseline for this session.

        Args:
            baseline_pose: np.array([pitch, yaw, roll]) — average head pose
                          when looking straight at the screen.
        """
        self.baseline_pose = baseline_pose.copy()
        self.deviation_start_time = None
        self.last_direction = "forward"

    def estimate(self, landmarks, image_width, image_height):
        """
        Estimate head pose from face landmarks.

        Args:
            landmarks: List of NormalizedLandmark from FaceLandmarker result (478 landmarks).
            image_width: Width of the input frame.
            image_height: Height of the input frame.

        Returns:
            dict with keys:
                - 'euler_angles': np.array([pitch, yaw, roll]) in degrees (smoothed)
                - 'raw_angles': np.array([pitch, yaw, roll]) in degrees (unsmoothed)
                - 'deviation': np.array([pitch_dev, yaw_dev, roll_dev]) from baseline
                - 'direction': str — 'forward', 'left', 'right', 'up', 'down', 'tilted'
                - 'is_violation': bool — True if sustained deviation exceeds threshold
                - 'violation_duration': float — seconds of sustained deviation
                - 'confidence': float — confidence of the pose estimate (0-1)
        """
        # Extract 2D landmark positions
        points_2d = self._extract_2d_points(landmarks, image_width, image_height)

        # Get camera matrix
        camera_matrix = self._get_camera_matrix(image_width, image_height)

        # Solve PnP
        raw_angles = self._solve_pose(points_2d, camera_matrix)

        if raw_angles is None:
            return {
                "euler_angles": np.array([0.0, 0.0, 0.0]),
                "raw_angles": np.array([0.0, 0.0, 0.0]),
                "deviation": np.array([0.0, 0.0, 0.0]),
                "direction": "unknown",
                "is_violation": False,
                "violation_duration": 0.0,
                "confidence": 0.0,
            }

        # Apply temporal smoothing
        smoothed = self._apply_smoothing(raw_angles)

        # Compute deviation from baseline using angular difference
        # (handles wrap-around correctly, e.g. 350° vs 10° = 20° diff)
        baseline = self.baseline_pose if self.baseline_pose is not None else np.array([0.0, 0.0, 0.0])
        deviation = np.array([
            self._angular_difference(smoothed[0], baseline[0]),
            self._angular_difference(smoothed[1], baseline[1]),
            self._angular_difference(smoothed[2], baseline[2]),
        ])

        # Classify head direction
        direction = self._classify_direction(deviation)

        # Check for sustained violation
        is_violation, violation_duration = self._check_sustained_deviation(direction)

        # Confidence based on how well landmarks were detected
        # Higher deviation = more confident in the direction classification
        max_dev = max(abs(deviation[0]) / PITCH_THRESHOLD, abs(deviation[1]) / YAW_THRESHOLD)
        confidence = min(1.0, max_dev)

        self.last_direction = direction

        return {
            "euler_angles": smoothed,
            "raw_angles": raw_angles,
            "deviation": deviation,
            "direction": direction,
            "is_violation": is_violation,
            "violation_duration": violation_duration,
            "confidence": confidence,
        }

    def _classify_direction(self, deviation):
        """
        Classify the head direction based on Euler angle deviation from baseline.

        Priority: yaw (left/right) first, then pitch (up/down).
        Roll (tilt) is NOT a standalone violation — slight tilting is
        natural and should never trigger by itself. It's only logged
        as supplementary information.
        """
        pitch_dev, yaw_dev, roll_dev = deviation[0], deviation[1], deviation[2]

        # Check yaw first (left/right turning is the primary cheating signal)
        if abs(yaw_dev) > YAW_THRESHOLD:
            return "left" if yaw_dev > 0 else "right"

        # Check pitch (up/down nodding)
        if abs(pitch_dev) > PITCH_THRESHOLD:
            return "up" if pitch_dev < 0 else "down"

        # Roll (tilt) is tracked but does NOT trigger a violation on its own.
        # Natural head tilting is extremely common and not a cheating signal.
        # It can be used as a secondary/combined signal in the violation logger.

        return "forward"

    def _check_sustained_deviation(self, direction):
        """
        Check if the candidate's head has been turned for longer than the threshold.

        Returns (is_violation: bool, duration: float)
        """
        current_time = time.time()

        if direction == "forward":
            # Reset deviation timer when facing screen
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

    def get_pose_landmarks_2d(self, landmarks, image_width, image_height):
        """
        Get the 2D pixel positions of the 6 pose reference landmarks.
        Useful for visualisation / drawing on the frame.

        Returns list of (x, y) tuples.
        """
        points = []
        for idx in POSE_LANDMARK_INDICES:
            lm = landmarks[idx]
            points.append((int(lm.x * image_width), int(lm.y * image_height)))
        return points

    def reset(self):
        """Reset the estimator state for a new session."""
        self.baseline_pose = None
        self.smoothed_angles = None
        self.deviation_start_time = None
        self.last_direction = "forward"
