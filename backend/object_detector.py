"""
ProctorVision — Object Detector Module
=========================================
Detects phones, books, earpieces, and counts people/faces using YOLOv8n.

Technical approach:
- Uses YOLOv8n with pretrained COCO weights for fast inference
- Target COCO classes:
    - class 0:  person    (multi-face / second person detection)
    - class 67: cell phone
    - class 73: book
    - class 63: laptop    (secondary device)
    - class 64: mouse     (not flagged, but tracked)
    - class 65: remote    (could indicate hidden device)
    - class 66: keyboard  (not flagged, but tracked)
- Confidence threshold: only fire if model confidence > 0.65
- Earpiece detection: ear region landmark occlusion heuristic (secondary signal)
- Runs at reduced frequency (every 5th frame) since objects move slowly

Note: YOLOv8n model will be auto-downloaded on first run (~6MB).
"""

import numpy as np
from ultralytics import YOLO

# COCO class IDs we care about
COCO_CLASSES = {
    0: "person",
    63: "laptop",
    65: "remote",
    67: "cell_phone",
    73: "book",
}

# Classes that trigger violations
VIOLATION_CLASSES = {
    "cell_phone": "phone_detected",
    "book": "suspicious_object",
    "laptop": "secondary_device",
    "remote": "suspicious_object",
}

# Minimum confidence to consider a detection valid
MIN_CONFIDENCE = 0.65

# Per-class confidence overrides — used when a class is prone to false positives.
# Phones in particular get confused with notebooks, dark books, remote-shaped
# rectangles, etc., so we require very high confidence before flagging.
CLASS_MIN_CONFIDENCE = {
    # Empirically, YOLOv8n on a 640x480 webcam frame scores a phone
    # held with its BACK toward the camera at 0.20-0.35 — way below
    # the COCO-trained sweet spot. Real cheating is rarely "phone
    # screen pointed at the webcam"; it's "phone held in lap or to
    # the side". We tolerate the false-positive cost of catching dark
    # wallets / notebooks at this threshold because the streak path
    # below corroborates real phones across multiple frames anyway.
    "cell_phone": 0.32,
    "book":       0.72,
}

# Minimum confidence for person detection (lower threshold since it's
# more about counting than precise detection)
PERSON_CONFIDENCE = 0.50

# Lower bound passed to YOLO at inference time. YOLO discards anything
# below this BEFORE we ever see it, so it must be ≤ the lowest per-class
# threshold above. Lowered to 0.18 so weak phone detections survive
# into the streak-path logic, which corroborates them across two
# YOLO calls.
INFERENCE_CONFIDENCE = 0.18

# Ear region landmarks for earpiece detection heuristic
# Left ear: landmarks around 234, 227, 137
# Right ear: landmarks around 454, 447, 366
LEFT_EAR_LANDMARKS = [234, 227, 137, 177, 147]
RIGHT_EAR_LANDMARKS = [454, 447, 366, 401, 376]


class ObjectDetector:
    """
    Detects objects of interest in the frame using YOLOv8n.

    Targets phones, books, secondary devices, and counts people for
    multi-face detection. Also provides an earpiece detection heuristic
    based on ear landmark occlusion patterns.
    """

    def __init__(self, model_path="yolov8n.pt"):
        """
        Initialize the YOLOv8n detector.

        Args:
            model_path: Path to YOLOv8n weights. Will auto-download
                       from Ultralytics hub if not found locally.
        """
        self.model = YOLO(model_path)
        self.model.fuse()  # Fuse Conv2d + BatchNorm2d for faster inference

        # Sustained-streak tracking for phone-shaped detections.
        # YOLOv8n at low confidence (0.30-0.40) catches more real phones
        # but also occasionally flickers on dark rectangular objects.
        # We accept any single detection >= 0.40, OR two consecutive
        # YOLO calls each at >= 0.30. The streak resets when no
        # phone-shaped class appears in a call.
        self._phone_streak_conf = 0.0  # peak confidence in last YOLO call

    def detect(self, frame):
        """
        Run object detection on a frame.

        Args:
            frame: BGR numpy array (OpenCV format) from webcam.

        Returns:
            dict with keys:
                - 'detections': list of detection dicts, each with:
                    - 'class_name': str
                    - 'confidence': float (0-1)
                    - 'bbox': [x1, y1, x2, y2] pixel coordinates
                    - 'is_violation': bool
                    - 'violation_type': str or None
                - 'person_count': int — number of people detected
                - 'has_phone': bool
                - 'has_book': bool
                - 'has_secondary_device': bool
                - 'multi_face_violation': bool — True if person_count > 1
        """
        # Run YOLO inference with stream=False for single frame
        results = self.model(frame, verbose=False, conf=INFERENCE_CONFIDENCE)

        detections = []
        person_count = 0
        has_phone = False
        has_book = False
        has_secondary_device = False

        # Track the highest "phone-shaped" confidence in THIS YOLO call so
        # we can update the cross-call streak at the end.
        phone_shaped_peak = 0.0
        # Streak bar: a phone-shaped detection at this confidence in two
        # consecutive YOLO calls qualifies as a violation. Lowered to
        # match the new INFERENCE_CONFIDENCE floor so weak (but
        # corroborated) detections still flag.
        SUSTAINED_PHONE_CONF = 0.20

        if results and len(results) > 0:
            result = results[0]  # Single frame result

            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]

                # Only process classes we care about
                if class_id not in COCO_CLASSES:
                    continue

                class_name = COCO_CLASSES[class_id]

                # Count persons
                if class_name == "person" and confidence >= PERSON_CONFIDENCE:
                    person_count += 1

                # Check if this is a violation-class detection
                is_violation = False
                violation_type = None

                # Track every "phone-shaped" candidate (cell_phone or
                # remote) at any confidence above the streak bar so we
                # can decide on the streak path below.
                if class_name in ("cell_phone", "remote") and confidence >= SUSTAINED_PHONE_CONF:
                    if confidence > phone_shaped_peak:
                        phone_shaped_peak = confidence

                required_conf = CLASS_MIN_CONFIDENCE.get(class_name, MIN_CONFIDENCE)
                hits_single_frame = (
                    class_name in VIOLATION_CLASSES and confidence >= required_conf
                )

                # Streak path: a phone-shaped detection at 0.30+ qualifies
                # if the PREVIOUS YOLO call also had a phone-shaped
                # detection at 0.30+. Two corroborating frames at low
                # confidence beats one frame at high confidence in
                # practice.
                hits_streak = (
                    class_name in ("cell_phone", "remote")
                    and confidence >= SUSTAINED_PHONE_CONF
                    and self._phone_streak_conf >= SUSTAINED_PHONE_CONF
                )

                if hits_single_frame or hits_streak:
                    is_violation = True
                    violation_type = VIOLATION_CLASSES.get(class_name, "phone_detected")

                    if class_name == "cell_phone":
                        has_phone = True
                    elif class_name == "book":
                        has_book = True
                    elif class_name == "laptop":
                        has_secondary_device = True
                    elif class_name == "remote":
                        # YOLO frequently misclassifies a phone-back (no
                        # screen visible) as a 'remote'. Treat a remote
                        # of reasonable confidence as a phone — no one's
                        # holding a TV remote during an online exam.
                        if confidence >= 0.40 or hits_streak:
                            violation_type = "phone_detected"
                            has_phone = True
                        else:
                            has_secondary_device = True

                detection = {
                    "class_name": class_name,
                    "confidence": confidence,
                    "bbox": [int(b) for b in bbox],
                    "is_violation": is_violation,
                    "violation_type": violation_type,
                }
                detections.append(detection)

        # Carry phone-shape evidence to the next YOLO call so the
        # streak path can corroborate two frames.
        self._phone_streak_conf = phone_shaped_peak

        return {
            "detections": detections,
            "person_count": person_count,
            "has_phone": has_phone,
            "has_book": has_book,
            "has_secondary_device": has_secondary_device,
            "multi_face_violation": person_count > 1,
        }

    def detect_earpiece(self, landmarks, image_width, image_height):
        """
        Heuristic earpiece detection based on ear landmark patterns.

        Checks if ear region landmarks show unusual clustering or occlusion
        that might indicate an in-ear device (AirPods, earbuds, etc.).

        This is a secondary signal — not as reliable as YOLO detection
        but adds an extra layer for audio cheating prevention.

        Args:
            landmarks: List of NormalizedLandmark from FaceLandmarker result.
            image_width: Width of the input frame.
            image_height: Height of the input frame.

        Returns:
            dict with keys:
                - 'left_ear_score': float (0-1) — likelihood of earpiece in left ear
                - 'right_ear_score': float (0-1) — likelihood of earpiece in right ear
                - 'earpiece_detected': bool — True if either ear scores above threshold
                - 'confidence': float (0-1)
        """
        def _compute_ear_spread(ear_landmarks):
            """
            Compute the spread/clustering of ear landmarks.
            
            Earpieces can cause landmarks to cluster abnormally due to
            occlusion of the ear region.
            """
            points = []
            for idx in ear_landmarks:
                if idx < len(landmarks):
                    lm = landmarks[idx]
                    points.append([lm.x * image_width, lm.y * image_height])

            if len(points) < 3:
                return 0.0

            points = np.array(points)

            # Compute the average pairwise distance between ear landmarks
            from itertools import combinations
            distances = [
                np.linalg.norm(points[i] - points[j])
                for i, j in combinations(range(len(points)), 2)
            ]

            avg_distance = np.mean(distances)
            std_distance = np.std(distances)

            # Lower spread (clustering) or high variance could indicate occlusion
            # This is a rough heuristic — normalise by image size
            normalised_spread = avg_distance / (image_width * 0.05)

            # Score: low spread = high likelihood of occlusion
            score = max(0.0, 1.0 - normalised_spread)
            return score

        left_score = _compute_ear_spread(LEFT_EAR_LANDMARKS)
        right_score = _compute_ear_spread(RIGHT_EAR_LANDMARKS)

        # Threshold for earpiece detection
        earpiece_threshold = 0.7
        earpiece_detected = left_score > earpiece_threshold or right_score > earpiece_threshold

        confidence = max(left_score, right_score) if earpiece_detected else 0.0

        return {
            "left_ear_score": left_score,
            "right_ear_score": right_score,
            "earpiece_detected": earpiece_detected,
            "confidence": confidence,
        }
