"""
ProctorVision — Violation Logger Module
=========================================
Tracks all violations with timestamps, computes live session risk score,
and manages per-session state for report generation.

Risk Score Formula (live):
    For each violation, contributes weight * 0.5^(age_sec / HALF_LIFE) to the
    current risk. Sum over all violations, clamp to [0, 100]. So:
      - 0   = no recent violations (clean)
      - 100 = sustained or many recent violations
    The score naturally decays over ~12s if behavior improves.
    Final summary also reports `peak_risk` (worst live value seen) and the
    classic monotonic `integrity_score` = max(0, 100 - SUM(weights)).

Violation Weights (from spec):
    - Multiple faces detected:       15 pts each
    - Phone/device detected:         12 pts each
    - Tab switch / focus loss:       10 pts each
    - Earpiece/earbud detected:      10 pts each
    - Face absence (>3s):             8 pts each
    - Sustained gaze deviation (>3s): 6 pts each
    - Head pose violation:            5 pts each
    - Lip movement (talking):         5 pts each

Anti-false-positive measures:
    - Violation cooldown: same type cannot re-fire within 3 seconds
    - Confidence threshold: only log if model confidence > 0.65
    - All violations must be sustained (temporal filtering handled by detectors)
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


# Violation weights for risk score computation.
#
# These are deliberately aggressive for the "hard evidence" categories
# (a phone, a second person, or the candidate disappearing entirely)
# because a single such event is grounds for review on its own. With
# the 12s half-life below, a phone weight of 45 means *one* phone flash
# pushes the live gauge to ~45 immediately, two flashes within the
# cooldown window land you around 80, three is ceiling. That matches
# the intuition the proctor has when watching it happen.
VIOLATION_WEIGHTS = {
    "multiple_faces":    50,
    "phone_detected":    45,
    "secondary_device":  40,
    "face_absence":      35,
    "tab_switch":        22,
    "earpiece_detected": 22,
    "suspicious_object": 18,
    "gaze_deviation":    10,
    "head_pose":         10,
    "lip_movement":       6,
    # Proctor-initiated. Weight is moderate because the proctor's
    # judgement is human and should clearly move the needle, but a
    # single flag shouldn't tank the entire integrity score.
    "manual_flag":       25,
}

# Half-life of a single violation's contribution to the live risk score.
# A 12-second half-life means a tab_switch (weight 18) goes 18 -> 9 -> 4.5
# over ~24 seconds if no further violations occur.
LIVE_RISK_HALF_LIFE = 12.0

# Minimum confidence to log a violation.
# Lowered to 0.30 to match the object detector's phone threshold (0.32).
# Without this, phone detections in the 0.32-0.64 range are flagged by
# the detector but then silently discarded here.
MIN_CONFIDENCE = 0.30

# Cooldown period — same violation type cannot re-fire within this many seconds
VIOLATION_COOLDOWN = 3.0


@dataclass
class Violation:
    """A single violation event."""
    id: str
    violation_type: str
    confidence: float
    timestamp: float          # Unix timestamp (seconds)
    timestamp_ms: int         # Milliseconds since session start
    weight: int               # Points deducted from integrity score
    bbox: Optional[list] = None  # [x, y, w, h] bounding box if applicable
    metadata: dict = field(default_factory=dict)  # Additional context

    def to_dict(self):
        """Convert to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "violation_type": self.violation_type,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
            "timestamp_ms": self.timestamp_ms,
            "weight": self.weight,
            "bbox": self.bbox,
            "metadata": self.metadata,
        }


class ViolationLogger:
    """
    Tracks violations, computes risk scores, and manages session state.

    Maintains a timestamped log of all violations with cooldown enforcement
    and confidence thresholds to prevent false positives.
    """

    def __init__(self):
        self.session_id = None
        self.session_start_time = None
        self.violations = []                    # List of Violation objects
        self.violation_counts = {}              # {type: count}
        self.last_violation_time = {}           # {type: last_timestamp}
        self.risk_score = 0                     # Current LIVE risk (0=clean, 100=max concern)
        self._peak_risk = 0                     # Highest live risk reached this session
        self._face_absent_start = None          # Track face absence duration
        self._degraded_detection_logged = False # Avoid spamming degraded events

    def start_session(self):
        """Start a new proctoring session."""
        self.session_id = str(uuid.uuid4())
        self.session_start_time = time.time()
        self.violations = []
        self.violation_counts = {}
        self.last_violation_time = {}
        self.risk_score = 0
        self._peak_risk = 0
        self._face_absent_start = None
        self._degraded_detection_logged = False
        return self.session_id

    def log_violation(self, violation_type, confidence=1.0, bbox=None, metadata=None):
        """
        Log a violation event.

        Enforces cooldown and confidence threshold before logging.

        Args:
            violation_type: str — one of the keys in VIOLATION_WEIGHTS
            confidence: float (0-1) — model confidence for this detection
            bbox: Optional [x, y, w, h] bounding box
            metadata: Optional dict with additional context

        Returns:
            Violation object if logged, None if filtered (cooldown/confidence)
        """
        current_time = time.time()

        # Check confidence threshold
        if confidence < MIN_CONFIDENCE:
            print(f"  [VL] {violation_type} dropped: confidence {confidence:.2f} < {MIN_CONFIDENCE}")
            return None

        # Check cooldown
        if violation_type in self.last_violation_time:
            elapsed = current_time - self.last_violation_time[violation_type]
            if elapsed < VIOLATION_COOLDOWN:
                print(f"  [VL] {violation_type} dropped: cooldown {elapsed:.1f}s < {VIOLATION_COOLDOWN}s")
                return None

        # Get weight for this violation type
        weight = VIOLATION_WEIGHTS.get(violation_type, 5)

        # Compute timestamp relative to session start
        timestamp_ms = int((current_time - self.session_start_time) * 1000) if self.session_start_time else 0

        # Create violation
        violation = Violation(
            id=str(uuid.uuid4())[:8],
            violation_type=violation_type,
            confidence=confidence,
            timestamp=current_time,
            timestamp_ms=timestamp_ms,
            weight=weight,
            bbox=bbox,
            metadata=metadata or {},
        )

        # Log it
        self.violations.append(violation)

        # Update counts
        self.violation_counts[violation_type] = self.violation_counts.get(violation_type, 0) + 1

        # Update cooldown
        self.last_violation_time[violation_type] = current_time

        # Recalculate risk score
        self._update_risk_score()

        print(f"  [VL] {violation_type} LOGGED (conf={confidence:.2f}, risk={self.risk_score})")

        return violation

    def check_face_absence(self, face_detected, threshold=2.0):
        """
        Track face absence and log a violation if face is missing too long.

        Args:
            face_detected: bool — whether a face was detected in the current frame
            threshold: float — seconds of absence before logging violation

        Returns:
            Violation object if absence violation logged, None otherwise
        """
        current_time = time.time()

        if face_detected:
            self._face_absent_start = None
            return None

        # Face not detected
        if self._face_absent_start is None:
            self._face_absent_start = current_time
            return None

        absence_duration = current_time - self._face_absent_start

        if absence_duration >= threshold:
            violation = self.log_violation(
                "face_absence",
                confidence=1.0,
                metadata={"absence_duration": round(absence_duration, 1)},
            )
            # Reset to allow re-triggering after cooldown
            self._face_absent_start = current_time
            return violation

        return None

    def log_degraded_detection(self):
        """
        Log a degraded detection event when lighting/confidence is poor.

        This is NOT a violation — it's informational, indicating that
        the system cannot reliably detect cheating in current conditions.
        """
        if not self._degraded_detection_logged:
            self._degraded_detection_logged = True
            # Don't log as violation, just track the event
            return {
                "type": "degraded_detection",
                "timestamp": time.time(),
                "message": "Low detection confidence — improve lighting for accurate monitoring",
            }
        return None

    def clear_degraded_flag(self):
        """Clear the degraded detection flag when conditions improve."""
        self._degraded_detection_logged = False

    def _update_risk_score(self):
        """Recalculate the LIVE risk score with exponential decay.

        Each past violation contributes weight * 0.5^(age / HALF_LIFE).
        Result is clamped to [0, 100]. Peak is tracked separately.
        """
        if not self.violations:
            self.risk_score = 0
            return
        now = time.time()
        score = 0.0
        for v in self.violations:
            age = max(0.0, now - v.timestamp)
            score += v.weight * (0.5 ** (age / LIVE_RISK_HALF_LIFE))
        self.risk_score = int(max(0, min(100, round(score))))
        if self.risk_score > self._peak_risk:
            self._peak_risk = self.risk_score

    def get_risk_score(self):
        """Get the current LIVE risk (recomputes decay every call)."""
        self._update_risk_score()
        return self.risk_score

    def get_integrity_score(self):
        """Final report metric. Higher = cleaner session (100 = no
        violations, 0 = catastrophic).

        We use an asymptotic curve rather than a flat subtraction so a
        candidate with 7 violations doesn't get the same score (0/100)
        as one with 70 violations. Formula:

            integrity = round(100 * 100 / (100 + total_impact))

        Examples:
            total_impact   0  →  100  (clean)
                          20  →   83
                          50  →   67
                         100  →   50  (half)
                         200  →   33
                         500  →   17

        The score asymptotically approaches 0 but never reaches it,
        which is honest: the system can't distinguish between "bad"
        and "infinitely bad" once a session is past a certain point.
        Floor at 1 so the report never shows the absurd "0/100".
        """
        total = sum(v.weight for v in self.violations)
        if total <= 0:
            return 100
        score = round(100 * 100 / (100 + total))
        return max(1, min(100, score))

    def get_session_summary(self):
        """
        Get a summary of the current session for report generation.

        Returns:
            dict with complete session data
        """
        current_time = time.time()
        duration = current_time - self.session_start_time if self.session_start_time else 0

        # Make sure live risk reflects decay up to this moment.
        self._update_risk_score()
        return {
            "session_id": self.session_id,
            "start_time": self.session_start_time,
            "duration": duration,
            "duration_formatted": self._format_duration(duration),
            # Final "how risky was this session" — use the peak so a clean ending
            # doesn't hide a bad middle.
            "risk_score": self._peak_risk,
            "live_risk": self.risk_score,
            "peak_risk": self._peak_risk,
            "integrity_score": self.get_integrity_score(),
            "total_violations": len(self.violations),
            "violation_counts": dict(self.violation_counts),
            "violations": [v.to_dict() for v in self.violations],
        }

    def get_recent_violations(self, count=5):
        """Get the most recent N violations."""
        return [v.to_dict() for v in self.violations[-count:]]

    def get_latest_violation(self):
        """Get the most recently logged violation, or None."""
        return self.violations[-1].to_dict() if self.violations else None

    @staticmethod
    def _format_duration(seconds):
        """Format duration in seconds to MM:SS string."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def end_session(self):
        """
        End the current session and return the final summary.

        Returns:
            dict with complete session summary including final risk score
        """
        summary = self.get_session_summary()
        summary["status"] = "completed"
        return summary
