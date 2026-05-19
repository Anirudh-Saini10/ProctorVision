"""
ProctorVision — CV Pipeline Module
=====================================
Orchestrates all CV modules into a single frame-processing pipeline.

Data flow per frame:
    Frame (JPEG bytes) → decode → MediaPipe FaceLandmarker → GazeEstimator
                                                           → HeadPoseEstimator
                                                           → LipMovementDetector
                                                           → Face count check
                                  → YOLOv8 (every Nth frame) → ObjectDetector
                                  → ViolationLogger (aggregate results)

Optimisations:
    - YOLO runs every 5th frame (objects move slowly)
    - MediaPipe runs every frame (gaze/pose need high frequency)
    - Low-confidence frames trigger degraded detection warning, not violations
    - Frame decoding happens once, shared across all modules
"""

import time
import base64
import numpy as np
import cv2
import os

from gaze_estimator import GazeEstimator
from head_pose_estimator import HeadPoseEstimator
from lip_movement_detector import LipMovementDetector
from object_detector import ObjectDetector
from calibration import CalibrationManager
from violation_logger import ViolationLogger

# Model paths
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
FACE_LANDMARKER_MODEL = os.path.join(MODEL_DIR, "face_landmarker.task")
YOLO_MODEL_PATH = os.path.join(os.path.dirname(__file__), "yolov8n.pt")


def _import_mediapipe():
    """Lazy-import mediapipe so a failed import doesn't block the whole module."""
    import mediapipe as mp
    return (
        mp.tasks.BaseOptions,
        mp.tasks.vision.FaceLandmarker,
        mp.tasks.vision.FaceLandmarkerOptions,
        mp.tasks.vision.RunningMode,
    )


def _check_model_files():
    """Verify ML model files exist on disk before attempting to load them."""
    missing = []
    if not os.path.isfile(FACE_LANDMARKER_MODEL):
        missing.append(FACE_LANDMARKER_MODEL)
    if not os.path.isfile(YOLO_MODEL_PATH):
        missing.append(YOLO_MODEL_PATH)
    if missing:
        raise FileNotFoundError(
            f"Missing model file(s): {missing}. "
            f"Expected face_landmarker.task at {FACE_LANDMARKER_MODEL} "
            f"and yolov8n.pt at {YOLO_MODEL_PATH}."
        )

# Processing frequency for YOLO (run every N frames). At 5fps frame
# streaming, 3 frames ≈ 600ms — a brief phone-flash gets ~2 chances to
# be caught instead of 1, which (combined with the streak-path logic
# in object_detector) makes phone detection noticeably more responsive.
YOLO_FRAME_INTERVAL = 3

# Minimum face detection confidence for reliable landmark data
MIN_FACE_CONFIDENCE = 0.5

# Minimum landmark count for iris tracking (need all 478 including iris)
MIN_LANDMARKS_FOR_IRIS = 478


class CVPipeline:
    """
    Unified computer vision pipeline for ProctorVision.

    Orchestrates MediaPipe FaceLandmarker, YOLOv8, and all detection
    modules. Manages calibration, processes frames, detects violations,
    and computes risk scores.

    Each session has its own pipeline instance with independent state.
    """

    def __init__(self):
        # Detection modules
        self.gaze = GazeEstimator()
        self.head_pose = HeadPoseEstimator()
        self.lip_detector = LipMovementDetector()
        self.object_detector = ObjectDetector(model_path=YOLO_MODEL_PATH)
        self.calibration = CalibrationManager()
        self.violation_logger = ViolationLogger()

        # MediaPipe FaceLandmarker (created on session start)
        self._landmarker = None

        # Frame counter for YOLO scheduling
        self._frame_count = 0
        self._start_ms = None

        # Last YOLO results (reused between YOLO frames)
        self._last_yolo_results = {
            "detections": [],
            "person_count": 0,
            "has_phone": False,
            "has_book": False,
            "has_secondary_device": False,
            "multi_face_violation": False,
        }

        # Session state
        self._session_active = False

        # Strictness preset for this session ('lenient'|'moderate'|'strict').
        # Set by the websocket handler at session_start. Currently used
        # to gate speaking-related violations (lip_movement / audio) so
        # they only fire under 'strict'.
        self.strictness = "moderate"

        # Sustained multi-face tracking. MediaPipe occasionally hallucinates
        # a second face on wall textures / posters at low confidence. We
        # require the second face to persist across multiple consecutive
        # frames before logging a violation.
        self._multi_face_streak = 0

    def start_session(self):
        """
        Start a new proctoring session.

        Initialises the FaceLandmarker, starts the violation logger,
        and begins the calibration phase.

        Returns:
            str: Session ID
        """
        # Validate model files are on disk before attempting to load them
        _check_model_files()

        # Lazy-import mediapipe so a container without libgomp1 / protobuf
        # issues can still import cv_pipeline for health checks.
        BaseOptions, FaceLandmarker, FaceLandmarkerOptions, RunningMode = _import_mediapipe()

        # Create FaceLandmarker
        # Close any existing landmarker before re-creating (important for
        # recalibration — a second start_session() on the same pipeline must
        # release the old MediaPipe resources).
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass
            self._landmarker = None

        try:
            options = FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=FACE_LANDMARKER_MODEL),
                running_mode=RunningMode.VIDEO,
                num_faces=2,  # Detect up to 2 faces for multi-face violation
                # Raised from 0.5 → 0.7 to stop hallucinating "second faces" on
                # wall posters, shadows and background textures. 0.7 still
                # reliably picks up an actual human face in frame.
                min_face_detection_confidence=0.7,
                min_face_presence_confidence=0.7,
                min_tracking_confidence=0.5,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
            )
            self._landmarker = FaceLandmarker.create_from_options(options)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create MediaPipe FaceLandmarker from {FACE_LANDMARKER_MODEL}. "
                f"Original error: {type(exc).__name__}: {exc}"
            ) from exc

        # Start session tracking
        session_id = self.violation_logger.start_session()
        self._frame_count = 0
        self._start_ms = int(time.time() * 1000)
        self._multi_face_streak = 0

        # Reset the one-shot "calibration_complete sent" flag so the WS
        # handler will emit calibration_complete when the NEW session's
        # calibration finishes. Without this, a recalibration never
        # resolves on the frontend.
        if hasattr(self, "_cal_complete_sent"):
            self._cal_complete_sent = False

        # Start calibration phase (resets baseline on detectors too)
        self.gaze.reset()
        self.head_pose.reset()
        self.lip_detector.reset()
        self.calibration.start()

        self._session_active = True
        return session_id

    def process_frame(self, frame_data, timestamp_ms=None):
        """
        Process a single frame through the entire CV pipeline.

        Args:
            frame_data: Either a numpy array (BGR) or base64-encoded JPEG string
            timestamp_ms: Timestamp in milliseconds (auto-computed if None)

        Returns:
            dict with keys:
                - 'violations': list of new violation dicts from this frame
                - 'risk_score': int (0-100) current session integrity score
                - 'calibration': dict with calibration progress/status
                - 'gaze': dict with gaze detection results (or None)
                - 'head_pose': dict with head pose results (or None)
                - 'lip_movement': dict with lip detection results (or None)
                - 'objects': dict with YOLO detection results
                - 'face_detected': bool
                - 'face_count': int
                - 'frame_number': int
                - 'degraded': bool — True if detection quality is poor
        """
        if not self._session_active:
            return {"error": "No active session"}

        self._frame_count += 1

        # Compute timestamp
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000) - self._start_ms

        # Decode frame if base64
        frame = self._decode_frame(frame_data)
        if frame is None:
            return {"error": "Failed to decode frame"}

        h, w = frame.shape[:2]

        # --- MediaPipe FaceLandmarker ---
        import mediapipe as _mp
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = _mp.Image(image_format=_mp.ImageFormat.SRGB, data=rgb_frame)

        face_result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        # Initialise results
        gaze_result = None
        head_pose_result = None
        lip_result = None
        new_violations = []
        face_detected = False
        face_count = 0
        degraded = False

        if face_result.face_landmarks and len(face_result.face_landmarks) > 0:
            face_detected = True
            face_count = len(face_result.face_landmarks)
            landmarks = face_result.face_landmarks[0]  # Primary face

            has_iris = len(landmarks) >= MIN_LANDMARKS_FOR_IRIS

            # --- Calibration phase ---
            if self.calibration.is_calibrating:
                if has_iris:
                    gaze_result = self.gaze.estimate(landmarks, w, h)
                    head_pose_result = self.head_pose.estimate(landmarks, w, h)

                    self.calibration.add_frame(
                        gaze_vector=gaze_result["gaze_vector"],
                        head_pose_angles=head_pose_result["euler_angles"],
                    )

                    # Check if calibration just completed
                    if self.calibration.is_complete:
                        baselines = self.calibration.get_baselines()
                        if baselines["is_valid"]:
                            self.gaze.set_baseline(baselines["gaze_baseline"])
                            self.head_pose.set_baseline(baselines["head_pose_baseline"])

            # --- Detection phase (after calibration) ---
            elif self.calibration.is_complete:
                # Run head pose first — it gates whether gaze data is trustworthy.
                head_pose_result = self.head_pose.estimate(landmarks, w, h)

                # When the head is turned beyond ~15 degrees, eye-width
                # denominators collapse and iris-offset values become
                # unreliable (they explode to >1.0 in profile view).
                # In that regime we let head_pose own the violation and
                # skip gaze entirely.
                #
                # Gate on baseline-RELATIVE deviation (the head_pose
                # estimator subtracts the user's calibrated neutral pose),
                # not raw absolute angles. This is critical: a user's
                # natural sitting posture often has +15-25 degrees of
                # absolute pitch due to camera position, but their pose
                # deviation from baseline is near zero — the head is
                # forward for them.
                hp_dev = head_pose_result.get("deviation") if head_pose_result else None
                head_is_forward = False
                if hp_dev is not None:
                    pitch_dev = float(hp_dev[0])
                    yaw_dev = float(hp_dev[1])
                    head_is_forward = abs(yaw_dev) < 15.0 and abs(pitch_dev) < 15.0

                # Compute gaze only when head is forward — keeps the
                # gaze signal clean and removes profile-view artifacts.
                if has_iris and head_is_forward:
                    gaze_result = self.gaze.estimate(landmarks, w, h)
                else:
                    # Reset the sustained-deviation timer so we don't carry
                    # state across a head turn.
                    self.gaze.deviation_start_time = None

                # NOTE: gaze_deviation violations are intentionally NOT
                # logged anymore. Pure eye-only gaze drift produced too many
                # false positives for students who naturally glance around,
                # rest their eyes, sulk, or look away to think during long
                # exams. We rely on head_pose violations instead — if a
                # student actually TURNS their head away from the screen
                # (to look at a phone, another screen, or a person), that
                # will flag. Small eye movements are allowed.
                if head_pose_result["is_violation"]:
                    v = self.violation_logger.log_violation(
                        "head_pose",
                        confidence=head_pose_result["confidence"],
                        metadata={"direction": head_pose_result["direction"],
                                  "duration": head_pose_result["violation_duration"]},
                    )
                    if v:
                        new_violations.append(v.to_dict())

                # Lip movement (every frame). The detector still RUNS
                # every frame because its smoothed MAR history is also
                # what gates audio-driven violations (`is_mouth_active`).
                # We just suppress the standalone silent-lip-sync
                # violation outside strict mode — talking to oneself is
                # tolerated in moderate / lenient sessions.
                lip_result = self.lip_detector.detect(landmarks, w, h)
                if (
                    lip_result["is_violation"]
                    and getattr(self, "strictness", "moderate") == "strict"
                ):
                    v = self.violation_logger.log_violation(
                        "lip_movement",
                        confidence=lip_result["confidence"],
                        metadata={"mar": lip_result["mar"],
                                  "duration": lip_result["violation_duration"],
                                  "source": "mar"},
                    )
                    if v:
                        new_violations.append(v.to_dict())

                # Multi-face check (from MediaPipe face count).
                # Require a SUSTAINED second-face detection across multiple
                # consecutive frames before flagging. MediaPipe can
                # briefly hallucinate a second face on wall art, posters,
                # patterned fabric or shadows; a real second person in
                # frame will persist. At ~5 fps, 8 frames ≈ 1.6 seconds.
                if face_count > 1:
                    self._multi_face_streak += 1
                else:
                    self._multi_face_streak = 0

                if self._multi_face_streak >= 8:
                    v = self.violation_logger.log_violation(
                        "multiple_faces",
                        confidence=1.0,
                        metadata={"face_count": face_count,
                                  "sustained_frames": self._multi_face_streak},
                    )
                    if v:
                        new_violations.append(v.to_dict())
                        # reset so the next violation also needs a fresh streak
                        self._multi_face_streak = 0

                # Clear degraded flag if detection is good
                self.violation_logger.clear_degraded_flag()

        else:
            # No face detected
            self._multi_face_streak = 0
            if self.calibration.is_complete:
                v = self.violation_logger.check_face_absence(face_detected=False)
                if v:
                    new_violations.append(v.to_dict())

        # --- YOLOv8 Object Detection (every Nth frame) ---
        if self._frame_count % YOLO_FRAME_INTERVAL == 0 and self.calibration.is_complete:
            yolo_results = self.object_detector.detect(frame)
            self._last_yolo_results = yolo_results

            # Log YOLO-detected violations
            for detection in yolo_results["detections"]:
                if detection["is_violation"]:
                    v = self.violation_logger.log_violation(
                        detection["violation_type"],
                        confidence=detection["confidence"],
                        bbox=detection["bbox"],
                        metadata={"class": detection["class_name"]},
                    )
                    if v:
                        new_violations.append(v.to_dict())

            # Multi-person from YOLO (backup for MediaPipe face count).
            # Also gated behind the sustained streak to avoid single-frame
            # YOLO false positives on mannequins, posters, or reflections.
            if (
                yolo_results["person_count"] > 1
                and face_count <= 1
                and self._multi_face_streak >= 4
            ):
                v = self.violation_logger.log_violation(
                    "multiple_faces",
                    confidence=0.8,
                    metadata={"source": "yolo", "person_count": yolo_results["person_count"]},
                )
                if v:
                    new_violations.append(v.to_dict())

            # Earpiece check (uses landmarks if available)
            if face_detected and face_result.face_landmarks:
                landmarks = face_result.face_landmarks[0]
                earpiece = self.object_detector.detect_earpiece(landmarks, w, h)
                if earpiece["earpiece_detected"]:
                    v = self.violation_logger.log_violation(
                        "earpiece_detected",
                        confidence=earpiece["confidence"],
                    )
                    if v:
                        new_violations.append(v.to_dict())

        # --- Build response ---
        calibration_info = self.calibration.get_progress()
        if self.calibration.is_complete and not calibration_info.get("baselines_sent"):
            calibration_info["baselines_sent"] = True

        return {
            "violations": new_violations,
            "risk_score": self.violation_logger.get_risk_score(),
            "calibration": calibration_info,
            "gaze": self._safe_result(gaze_result),
            "head_pose": self._safe_result(head_pose_result),
            "lip_movement": self._safe_result(lip_result),
            "objects": self._last_yolo_results,
            "face_detected": face_detected,
            "face_count": face_count,
            "frame_number": self._frame_count,
            "degraded": degraded,
        }

    def _decode_frame(self, frame_data):
        """
        Decode frame from either numpy array or base64 JPEG.

        Args:
            frame_data: numpy array (BGR) or base64-encoded JPEG string

        Returns:
            numpy array (BGR) or None if decoding fails
        """
        if isinstance(frame_data, np.ndarray):
            return frame_data

        if isinstance(frame_data, str):
            try:
                # Remove data URL prefix if present
                if "," in frame_data:
                    frame_data = frame_data.split(",", 1)[1]

                jpeg_bytes = base64.b64decode(frame_data)
                np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                return frame
            except Exception as e:
                print(f"Frame decode error: {e}")
                return None

        return None

    @staticmethod
    def _safe_result(result):
        """
        Convert detection result to JSON-safe format.

        Converts numpy arrays to lists for JSON serialization.
        """
        if result is None:
            return None

        safe = {}
        for key, value in result.items():
            if isinstance(value, np.ndarray):
                safe[key] = value.tolist()
            else:
                safe[key] = value
        return safe

    def end_session(self):
        """
        End the current proctoring session.

        Closes the FaceLandmarker and returns the final session summary.

        Returns:
            dict with complete session summary
        """
        if self._landmarker:
            self._landmarker.close()
            self._landmarker = None

        self._session_active = False

        summary = self.violation_logger.end_session()

        # Reset all detectors
        self.gaze.reset()
        self.head_pose.reset()
        self.lip_detector.reset()
        self.calibration.reset()

        return summary

    def get_session_summary(self):
        """Get current session summary without ending it."""
        return self.violation_logger.get_session_summary()
