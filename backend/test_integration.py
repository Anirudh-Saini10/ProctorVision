"""
ProctorVision — Full Backend Integration Test
"""
print("=" * 60)
print("  ProctorVision Backend — Full Integration Check")
print("=" * 60)
print()

# 1. All module imports
print("[1/6] Testing all module imports...")
from gaze_estimator import GazeEstimator
from head_pose_estimator import HeadPoseEstimator
from lip_movement_detector import LipMovementDetector
from object_detector import ObjectDetector
from calibration import CalibrationManager
from violation_logger import ViolationLogger
from cv_pipeline import CVPipeline
from report_generator import generate_report
from websocket_handler import WebSocketHandler
print("  All 9 modules imported OK")

# 2. Instantiation
print("[2/6] Instantiating all modules...")
gaze = GazeEstimator()
head = HeadPoseEstimator()
lip = LipMovementDetector()
obj = ObjectDetector()
cal = CalibrationManager()
vl = ViolationLogger()
pipeline = CVPipeline()
ws = WebSocketHandler()
print("  All modules instantiated OK")

# 3. Violation logger flow
print("[3/6] Testing violation logger flow...")
sid = vl.start_session()
v1 = vl.log_violation("phone_detected", confidence=0.9)
v2 = vl.log_violation("gaze_deviation", confidence=0.8)
v3 = vl.log_violation("phone_detected", confidence=0.95)  # blocked by cooldown
assert v1 is not None, "v1 should log"
assert v2 is not None, "v2 should log"
assert v3 is None, "v3 should be blocked by cooldown"
assert vl.get_risk_score() == 82, f"Expected 82, got {vl.get_risk_score()}"
summary = vl.get_session_summary()
assert summary["total_violations"] == 2
print(f"  Risk score: {vl.get_risk_score()}/100, violations: {summary['total_violations']}")
print("  Cooldown working correctly")

# 4. Calibration flow
print("[4/6] Testing calibration flow...")
import numpy as np
import time
cal2 = CalibrationManager(duration=0.1, min_frames=3)
cal2.start()
assert cal2.is_calibrating
for i in range(10):
    cal2.add_frame(
        gaze_vector=np.array([0.05 + i * 0.001, -0.02]),
        head_pose_angles=np.array([2.0 + i * 0.1, -1.0, 0.5]),
    )
time.sleep(0.15)
cal2.add_frame(
    gaze_vector=np.array([0.05, -0.02]),
    head_pose_angles=np.array([2.0, -1.0, 0.5]),
)
assert cal2.is_complete, f"Expected complete, got {cal2.state}"
baselines = cal2.get_baselines()
assert baselines["is_valid"], "Baselines should be valid"
print(f"  Gaze baseline: {baselines['gaze_baseline']}")
print(f"  Pose baseline: {baselines['head_pose_baseline']}")

# 5. PDF report
print("[5/6] Testing PDF report generation...")
summary_for_report = vl.end_session()
pdf = generate_report(summary_for_report)
assert len(pdf) > 1000, f"PDF too small: {len(pdf)} bytes"
print(f"  PDF generated: {len(pdf)} bytes")

# 6. Head pose angle normalization
print("[6/6] Testing head pose angle math...")
hp = HeadPoseEstimator()
assert hp._normalize_angle(179.5) == 179.5
assert hp._normalize_angle(360.0) == 0.0
assert hp._normalize_angle(-180.0) == -180.0
assert abs(hp._angular_difference(350, 10) - (-20)) < 0.01
assert abs(hp._angular_difference(10, 350) - 20) < 0.01
assert abs(hp._angular_difference(179, -179) - (-2)) < 0.01
print("  Angle normalization and angular difference: OK")

print()
print("=" * 60)
print("  ALL 6 CHECKS PASSED")
print("=" * 60)
