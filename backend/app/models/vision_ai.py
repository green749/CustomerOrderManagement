from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, Index
from .base import Base


def utcnow():
    return datetime.now(timezone.utc)


class AIDetection(Base):
    """Raw AI Vision Model Inferences."""
    __tablename__ = "ai_detection"

    detection_id = Column(String(36), primary_key=True, index=True)
    image_id = Column(String(36), nullable=True, index=True)
    category_id = Column(String(48), nullable=False, index=True)  # crack, scratch, dent
    bbox = Column(JSON, nullable=True)  # [x, y, w, h] normalized
    confidence = Column(Float, nullable=False, default=0.0)
    proposed_severity = Column(String(16), nullable=False, default="Low")  # Critical, High, Medium, Low
    model_name = Column(String(64), nullable=False, default="YOLOv8-SurfaceInspection")
    model_version = Column(String(32), nullable=False, default="2.0")
    is_simulated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class DefectInstance(Base):
    """Consolidated Agent Defect Findings mapped to product 3D surface zones."""
    __tablename__ = "defect_instance"

    defect_id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    product_id = Column(String(50), nullable=True, index=True)
    category_id = Column(String(48), nullable=False, index=True)
    zone_id = Column(String(36), nullable=True, index=True)  # Surface zone ID
    is_unassigned = Column(Boolean, nullable=False, default=False)
    view = Column(String(16), nullable=False, default="top")  # front, back, left, right, top, bottom
    product_coords = Column(JSON, nullable=True)  # {"cx", "cy", "w", "h"}
    area_frac = Column(Float, nullable=True, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)
    severity_ai = Column(String(16), nullable=False, default="Low")
    severity_rule = Column(String(16), nullable=False, default="Low")
    severity_final = Column(String(16), nullable=False, default="Low", index=True)  # Critical, High, Medium, Low
    verification_status = Column(String(24), nullable=False, default="unverified")  # unverified, confirmed, rejected, reclassified
    source = Column(String(16), nullable=False, default="ai")  # ai, manual_addition
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Disposition(Base):
    """AI Recommended Disposition & Explainable Rule Trace."""
    __tablename__ = "disposition"

    disposition_id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(36), nullable=False, unique=True, index=True)
    product_id = Column(String(50), nullable=True, index=True)
    recommended = Column(String(16), nullable=False, default="Release", index=True)  # Release, Rework, Hold, Scrap
    rule_trace = Column(JSON, nullable=True)
    ai_explanation = Column(Text, nullable=True)
    explanation_source = Column(String(24), nullable=False, default="hybrid")  # rules, model, hybrid
    severity_summary = Column(JSON, nullable=True)
    is_borderline = Column(Boolean, nullable=False, default=False)
    computed_at = Column(DateTime, nullable=False, default=utcnow)


class Approval(Base):
    """Segregation-of-Duties Sign-off on Inspection Outcome."""
    __tablename__ = "approval"

    approval_id = Column(String(36), primary_key=True, index=True)
    disposition_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    approver_user_id = Column(String(36), nullable=False)
    decision = Column(String(16), nullable=False)  # Release, Rework, Hold, Scrap
    is_override = Column(Boolean, nullable=False, default=False)
    override_reason = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=False, default=utcnow)


class VisionAlert(Base):
    """Automated Agent Monitoring & Anomaly Triggers."""
    __tablename__ = "vision_ai_alerts"

    alert_id = Column(String(36), primary_key=True, index=True)
    fingerprint = Column(String(160), nullable=True, index=True)
    rule_id = Column(String(48), nullable=False, index=True)
    rule_name = Column(String(160), nullable=False)
    severity = Column(String(16), nullable=False, default="WARNING")  # INFO, WARNING, CRITICAL
    scope = Column(JSON, nullable=True)  # {"plant", "line_id", "product_id"}
    metric = Column(String(64), nullable=True)
    observed = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    title = Column(String(240), nullable=False)
    detail = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    status = Column(String(16), nullable=False, default="open", index=True)  # open, acknowledged, resolved, suppressed
    first_seen = Column(DateTime, nullable=False, default=utcnow)
    last_seen = Column(DateTime, nullable=False, default=utcnow)


class VisionAuditLog(Base):
    """Append-Only Audit Trail."""
    __tablename__ = "vision_ai_audit_log"

    event_id = Column(String(36), primary_key=True, index=True)
    entity = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False)
    action = Column(String(48), nullable=False)
    user = Column(String(120), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=utcnow)
