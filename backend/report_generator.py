"""
ProctorVision — Report Generator Module
==========================================
Generates post-session PDF integrity reports using ReportLab.

Report contents:
    - Session header with ID, date/time, duration
    - Overall integrity score (large, prominent)
    - Violation summary table (type, count, total weight)
    - Detailed violation timeline (timestamp, type, confidence)
    - Risk assessment classification (Low / Medium / High / Critical)
"""

import io
import time
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Violation display names
VIOLATION_DISPLAY_NAMES = {
    "multiple_faces": "Multiple Faces Detected",
    "phone_detected": "Phone / Device Detected",
    "tab_switch": "Tab Switch / Focus Loss",
    "earpiece_detected": "Earpiece / Earbud Detected",
    "face_absence": "Face Absence",
    "gaze_deviation": "Sustained Gaze Deviation",
    "head_pose": "Head Pose Violation",
    "lip_movement": "Lip Movement (Talking)",
    "suspicious_object": "Suspicious Object (Book/Notes)",
    "secondary_device": "Secondary Device Detected",
}


def _get_risk_level(score):
    """Classify the risk level based on integrity score."""
    if score >= 85:
        return "LOW RISK", colors.HexColor("#22c55e")
    elif score >= 65:
        return "MEDIUM RISK", colors.HexColor("#f59e0b")
    elif score >= 40:
        return "HIGH RISK", colors.HexColor("#ef4444")
    else:
        return "CRITICAL RISK", colors.HexColor("#dc2626")


def generate_report(session_summary):
    """
    Generate a PDF integrity report from session data.

    Args:
        session_summary: dict from ViolationLogger.get_session_summary()
            Expected keys: session_id, start_time, duration,
            duration_formatted, risk_score, total_violations,
            violation_counts, violations

    Returns:
        bytes: PDF file content as bytes
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    # --- Styles ---
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=24,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
        spaceAfter=20,
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=16,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#334155"),
        leading=14,
    )

    score_style = ParagraphStyle(
        "ScoreStyle",
        parent=styles["Title"],
        fontSize=48,
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    # --- Build document elements ---
    elements = []

    # Header
    elements.append(Paragraph("PROCTORVISION", title_style))
    elements.append(Paragraph("Session Integrity Report", subtitle_style))
    elements.append(HRFlowable(
        width="100%", thickness=2,
        color=colors.HexColor("#3b82f6"),
        spaceAfter=16,
    ))

    # Session info
    session_id = session_summary.get("session_id", "N/A")
    start_time = session_summary.get("start_time", 0)
    duration_fmt = session_summary.get("duration_formatted", "00:00")
    start_dt = datetime.fromtimestamp(start_time) if start_time else datetime.now()

    info_data = [
        ["Session ID", session_id[:16] + "..." if len(session_id) > 16 else session_id],
        ["Date", start_dt.strftime("%B %d, %Y")],
        ["Time", start_dt.strftime("%I:%M %p")],
        ["Duration", duration_fmt],
        ["Total Violations", str(session_summary.get("total_violations", 0))],
    ]

    info_table = Table(info_data, colWidths=[120, 350])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 16))

    # Integrity Score (big and prominent)
    risk_score = session_summary.get("risk_score", 100)
    risk_level, risk_color = _get_risk_level(risk_score)

    score_style_colored = ParagraphStyle(
        "ScoreColored",
        parent=score_style,
        textColor=risk_color,
    )

    elements.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#e2e8f0"),
        spaceBefore=8, spaceAfter=12,
    ))

    elements.append(Paragraph("SESSION INTEGRITY SCORE", ParagraphStyle(
        "ScoreLabel", parent=subtitle_style, fontSize=12, spaceAfter=4,
    )))
    elements.append(Paragraph(f"{risk_score}/100", score_style_colored))
    elements.append(Paragraph(risk_level, ParagraphStyle(
        "RiskLevel", parent=subtitle_style,
        fontSize=14, textColor=risk_color,
        spaceAfter=8,
    )))
    elements.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#e2e8f0"),
        spaceBefore=8, spaceAfter=16,
    ))

    # Violation Summary Table
    violation_counts = session_summary.get("violation_counts", {})

    if violation_counts:
        elements.append(Paragraph("Violation Summary", heading_style))

        summary_header = ["Violation Type", "Count", "Weight Each", "Total Impact"]
        summary_rows = [summary_header]

        from violation_logger import VIOLATION_WEIGHTS

        for v_type, count in sorted(violation_counts.items(), key=lambda x: -x[1]):
            display_name = VIOLATION_DISPLAY_NAMES.get(v_type, v_type.replace("_", " ").title())
            weight = VIOLATION_WEIGHTS.get(v_type, 5)
            total = weight * count
            summary_rows.append([display_name, str(count), str(weight), str(total)])

        # Add total row
        total_impact = sum(
            VIOLATION_WEIGHTS.get(v_type, 5) * count
            for v_type, count in violation_counts.items()
        )
        summary_rows.append(["TOTAL", str(sum(violation_counts.values())), "", str(total_impact)])

        summary_table = Table(summary_rows, colWidths=[200, 60, 80, 80])
        summary_table.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGNMENT", (1, 0), (-1, -1), "CENTER"),
            # Body
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TEXTCOLOR", (0, 1), (-1, -2), colors.HexColor("#334155")),
            # Alternating rows
            ("BACKGROUND", (0, 1), (-1, -2), colors.HexColor("#f8fafc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.HexColor("#f8fafc"), colors.white]),
            # Total row
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#1e293b")),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

    # Detailed Violation Timeline
    violations = session_summary.get("violations", [])

    if violations:
        elements.append(Paragraph("Violation Timeline", heading_style))

        timeline_header = ["Time", "Type", "Confidence", "Details"]
        timeline_rows = [timeline_header]

        for v in violations:
            # Format timestamp
            ts_ms = v.get("timestamp_ms", 0)
            minutes = ts_ms // 60000
            seconds = (ts_ms % 60000) // 1000
            time_str = f"{minutes:02d}:{seconds:02d}"

            v_type = v.get("violation_type", "unknown")
            display_name = VIOLATION_DISPLAY_NAMES.get(v_type, v_type.replace("_", " ").title())
            confidence = f"{v.get('confidence', 0) * 100:.0f}%"

            # Build details string from metadata
            metadata = v.get("metadata", {})
            details_parts = []
            if "direction" in metadata:
                details_parts.append(f"Dir: {metadata['direction']}")
            if "face_count" in metadata:
                details_parts.append(f"Faces: {metadata['face_count']}")
            if "duration" in metadata:
                details_parts.append(f"Dur: {metadata['duration']:.1f}s")
            if "source" in metadata:
                details_parts.append(f"Src: {metadata['source']}")
            details = ", ".join(details_parts) if details_parts else "-"

            timeline_rows.append([time_str, display_name, confidence, details])

        timeline_table = Table(timeline_rows, colWidths=[50, 170, 70, 130])
        timeline_table.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGNMENT", (0, 0), (0, -1), "CENTER"),
            ("ALIGNMENT", (2, 0), (2, -1), "CENTER"),
            # Body
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#334155")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(timeline_table)
    else:
        elements.append(Paragraph("Violation Timeline", heading_style))
        elements.append(Paragraph(
            "No violations were detected during this session.",
            body_style,
        ))

    # Footer
    elements.append(Spacer(1, 30))
    elements.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#e2e8f0"),
        spaceBefore=8, spaceAfter=8,
    ))
    elements.append(Paragraph(
        f"Generated by ProctorVision • {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        ParagraphStyle("Footer", parent=subtitle_style, fontSize=8, spaceAfter=0),
    ))

    # Build PDF
    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
