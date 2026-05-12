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

# Minimum confidence for person detection (lower threshold since it's
# more about counting than precise detection)
PERSON_CONFIDENCE = 0.50

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
        results = self.model(frame, verbose=False, conf=PERSON_CONFIDENCE)

        detections = []
        person_count = 0
        has_phone = False
        has_book = False
        has_secondary_device = False

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

                if class_name in VIOLATION_CLASSES and confidence >= MIN_CONFIDENCE:
                    is_violation = True
                    violation_type = VIOLATION_CLASSES[class_name]

                    if class_name == "cell_phone":
                        has_phone = True
                    elif class_name == "book":
                        has_book = True
                    elif class_name in ("laptop", "remote"):
                        has_secondary_device = True

                detection = {
                    "class_name": class_name,
                    "confidence": confidence,
                    "bbox": [int(b) for b in bbox],
                    "is_violation": is_violation,
                    "violation_type": violation_type,
                }
                detections.append(detection)

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
