from datetime import datetime, date, timezone
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Index, Text, JSON, Boolean, Numeric, Float
from sqlalchemy.orm import relationship, foreign
from .base import Base


def utcnow():
    return datetime.now(timezone.utc)


class CommitmentProposal(Base):
    __tablename__ = "commitment_proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_order_id = Column(String(50), nullable=False, index=True)
    proposed_date = Column(Date, nullable=False)
    recommended_by = Column(String(50), nullable=False, default="agent")  # 'agent' | 'user'
    reasons = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="PENDING", index=True)  # PENDING | APPROVED | REJECTED
    revised_estimated_date = Column(Date, nullable=True)
    delay_days = Column(Integer, nullable=True)
    verdict = Column(String(20), nullable=True)  # ON_TIME | DELAYED | AT_RISK
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_note = Column(Text, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    decider = relationship("User", foreign_keys=[decided_by])
    assessments = relationship("OrderAssessment", back_populates="proposal")

    __table_args__ = (
        Index("idx_order_revision", "customer_order_id", "revision"),
        Index("idx_proposal_status", "status"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(100), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    user = relationship("User", foreign_keys=[user_id])


# ==============================================================================
# AGENT 2: ORDER FEASIBILITY & COMMITMENT MODELS
# ==============================================================================

class OrderAssessment(Base):
    __tablename__ = "order_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(String(50), nullable=False, index=True)
    product_id = Column(String(50), nullable=False, index=True)
    order_qty = Column(Integer, nullable=False)
    requested_delivery_date = Column(Date, nullable=False, index=True)
    unit_price_inr = Column(Numeric(12, 2), nullable=True)
    priority = Column(String(50), nullable=False, default="MEDIUM")
    channel = Column(String(50), nullable=False, default="EDI")
    ship_to = Column(String(255), nullable=True)
    product_config = Column(JSON, nullable=True)
    packaging_req = Column(String(255), nullable=True)

    # Assessment Results
    overall_status = Column(String(50), nullable=False, default="INSUFFICIENT_DATA", index=True)
    # FEASIBLE | FEASIBLE_WITH_RISKS | AT_RISK | NOT_FEASIBLE | INSUFFICIENT_DATA
    estimated_delivery_date = Column(Date, nullable=True)
    days_variance = Column(Integer, nullable=True)  # estimated - requested (positive = delay)
    confidence_level = Column(String(50), nullable=False, default="MEDIUM")  # HIGH | MEDIUM | LOW
    blockers_summary = Column(JSON, nullable=True)
    corrective_actions_summary = Column(JSON, nullable=True)
    missing_data = Column(JSON, nullable=True)
    agent_reasoning = Column(JSON, nullable=True)
    agent_output = Column(JSON, nullable=True)
    agent_disagreement = Column(Boolean, nullable=False, default=False)
    result_source = Column(String(20), nullable=False, default="RULES_FALLBACK")  # AGENT | RULES_FALLBACK | RULES
    agent_status = Column(String(50), nullable=True, default="rules_mode")  # success | rules_mode | ai_unavailable | rate_limit_paused | validation_failed_twice | error
    revised_estimated_date = Column(Date, nullable=True)
    delay_days = Column(Integer, nullable=True)
    verdict = Column(String(20), nullable=True)  # ON_TIME | DELAYED | AT_RISK

    # Workflow links
    proposal_id = Column(Integer, ForeignKey("commitment_proposals.id", ondelete="SET NULL"), nullable=True)
    customer_order_id = Column(String(50), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    proposal = relationship("CommitmentProposal", back_populates="assessments")
    creator = relationship("User", foreign_keys=[created_by])
    customer = relationship(
        "DimCustomer",
        primaryjoin="foreign(OrderAssessment.customer_id) == DimCustomer.customer_id",
        viewonly=True,
    )
    product = relationship(
        "DimProduct",
        primaryjoin="foreign(OrderAssessment.product_id) == DimProduct.product_id",
        viewonly=True,
    )
    readiness_records = relationship(
        "DepartmentReadiness",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="DepartmentReadiness.department",
    )

    @property
    def customer_name(self) -> Optional[str]:
        return self.customer.customer_name if self.customer else None

    @property
    def product_name(self) -> Optional[str]:
        return self.product.product_name if self.product else None

    @property
    def departments_evaluated(self) -> List[str]:
        if self.agent_output and isinstance(self.agent_output, dict):
            if "departments_evaluated" in self.agent_output:
                return self.agent_output["departments_evaluated"]
        return [r.department for r in self.readiness_records if r.readiness_status != "NOT_EVALUATED"]

    @property
    def stopped_early(self) -> bool:
        if self.agent_output and isinstance(self.agent_output, dict):
            return bool(self.agent_output.get("stopped_early", False))
        return False

    @property
    def stop_reason(self) -> Optional[str]:
        if self.agent_output and isinstance(self.agent_output, dict):
            return self.agent_output.get("stop_reason")
        return None


class DepartmentReadiness(Base):
    __tablename__ = "department_readiness"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("order_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    department = Column(String(50), nullable=False, index=True)  # ERP, MMS, MES, WMS, QMS, TMS, PLM
    readiness_status = Column(String(50), nullable=False, index=True)
    # READY | PARTIALLY_READY | NOT_READY | BLOCKED | INSUFFICIENT_DATA | NOT_APPLICABLE
    available_evidence = Column(JSON, nullable=True)
    identified_issue = Column(Text, nullable=True)
    reason_for_issue = Column(Text, nullable=True)
    required_action = Column(Text, nullable=True)
    responsible_role = Column(String(100), nullable=True)
    estimated_delay_days = Column(Integer, nullable=True)
    data_source = Column(String(150), nullable=True)
    last_updated_at = Column(DateTime, nullable=False, default=utcnow)
    missing_info = Column(Text, nullable=True)

    assessment = relationship("OrderAssessment", back_populates="readiness_records")

    __table_args__ = (
        Index("idx_dept_readiness_assessment", "assessment_id", "department"),
    )


# ==============================================================================
# AGENT 3: ORDER MONITORING & RISK MANAGEMENT MODELS
# ==============================================================================

class OrderMonitoringRecord(Base):
    __tablename__ = "order_monitoring_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_order_id = Column(String(50), unique=True, nullable=False, index=True)
    approved_delivery_date = Column(Date, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="ACTIVE", index=True)  # ACTIVE | DELIVERED | CANCELLED
    baseline_milestones = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=False, default=utcnow)
    last_checked_at = Column(DateTime, nullable=True, index=True)
    closed_at = Column(DateTime, nullable=True)
    closure_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    alerts = relationship("RiskAlert", back_populates="monitoring_record")
    execution_logs = relationship("MonitoringExecutionLog", back_populates="monitoring_record", cascade="all, delete-orphan")


class MonitoringExecutionLog(Base):
    __tablename__ = "monitoring_execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    monitoring_record_id = Column(Integer, ForeignKey("order_monitoring_records.id", ondelete="CASCADE"), nullable=True, index=True)
    customer_order_id = Column(String(50), nullable=True, index=True)
    cycle_type = Column(String(50), nullable=False, default="SCHEDULED")  # SCHEDULED | MANUAL
    started_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String(50), nullable=False, default="SUCCESS")  # SUCCESS | FAILURE | SKIPPED
    risks_found_count = Column(Integer, nullable=False, default=0)
    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    monitoring_record = relationship("OrderMonitoringRecord", back_populates="execution_logs")


class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_order_id = Column(String(50), nullable=False, index=True)
    monitoring_record_id = Column(Integer, ForeignKey("order_monitoring_records.id", ondelete="SET NULL"), nullable=True, index=True)
    department = Column(String(50), nullable=False, index=True)  # ERP, MMS, MES, WMS, QMS, TMS, PLM
    risk_category = Column(String(100), nullable=False, index=True)  # MATERIAL_SHORTAGE, PRODUCTION_DELAY, QUALITY_HOLD, SHIPMENT_DELAY, etc.
    severity = Column(String(50), nullable=False, index=True)  # CRITICAL, HIGH, MEDIUM, LOW
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    delivery_impact = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="OPEN", index=True)  # OPEN | ACKNOWLEDGED | RESOLVED
    result_source = Column(String(20), nullable=False, default="RULES_FALLBACK")  # AGENT | RULES_FALLBACK
    assigned_owner = Column(String(255), nullable=True)
    dedup_fingerprint = Column(String(255), nullable=False, index=True)
    detected_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Customer Service Communication Tracking
    customer_communicated = Column(Boolean, nullable=False, default=False)
    customer_communication_notes = Column(Text, nullable=True)
    customer_communicated_at = Column(DateTime, nullable=True)
    customer_communicated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    monitoring_record = relationship("OrderMonitoringRecord", back_populates="alerts")
    notifications = relationship("EmailNotificationLog", back_populates="alert")
    acknowledger = relationship("User", foreign_keys=[acknowledged_by])
    resolver = relationship("User", foreign_keys=[resolved_by])
    customer_communicator = relationship("User", foreign_keys=[customer_communicated_by])

    @property
    def first_email_sent_at(self) -> Optional[datetime]:
        if self.notifications:
            risk_notifs = [n for n in self.notifications if n.notification_type in ("ACTION_REQUIRED", "DELIVERY_RISK") and n.status in ("SENT", "PENDING_CONFIG")]
            if risk_notifs:
                first = min(risk_notifs, key=lambda n: n.created_at)
                return first.sent_at or first.created_at
        return None

    @property
    def followup_sent_at(self) -> Optional[datetime]:
        if self.notifications:
            fu_notifs = [n for n in self.notifications if n.notification_type in ("FOLLOW_UP", "RISK_FOLLOW_UP", "ESCALATION_FOLLOW_UP") and n.status in ("SENT", "PENDING_CONFIG")]
            if fu_notifs:
                latest = max(fu_notifs, key=lambda n: n.created_at)
                return latest.sent_at or latest.created_at
        return None

    @property
    def followup_count(self) -> int:
        if self.notifications:
            return sum(1 for n in self.notifications if n.notification_type in ("FOLLOW_UP", "RISK_FOLLOW_UP", "ESCALATION_FOLLOW_UP") and n.status in ("SENT", "PENDING_CONFIG"))
        return 0

    @property
    def days_unresolved(self) -> Optional[int]:
        if self.status == "RESOLVED":
            return None
        f_time = self.first_email_sent_at or self.detected_at
        if f_time:
            now = utcnow()
            if f_time.tzinfo is None:
                f_time = f_time.replace(tzinfo=timezone.utc)
            return max(0, int((now - f_time).total_seconds() / 86400.0))
        return None

    @property
    def is_followup_due(self) -> bool:
        if self.status == "RESOLVED":
            return False
        days = self.days_unresolved
        return days is not None and days >= 3


class EmailNotificationLog(Base):
    __tablename__ = "email_notification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("risk_alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_order_id = Column(String(50), nullable=False, index=True)
    recipient_email = Column(String(255), nullable=False, index=True)
    recipient_category = Column(String(50), nullable=False, default="OPERATIONAL", index=True)  # OPERATIONAL | CUSTOMER_SERVICE
    notification_type = Column(String(50), nullable=False, default="ACTION_REQUIRED", index=True)  # ACTION_REQUIRED | DELIVERY_RISK | ESCALATION | RESOLVED
    department = Column(String(50), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    body_text = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="PENDING_CONFIG", index=True)  # SENT | FAILED | RETRYING | PENDING_CONFIG
    retry_count = Column(Integer, nullable=False, default=0)
    failure_reason = Column(Text, nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    last_attempt_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)

    alert = relationship("RiskAlert", back_populates="notifications")


class DepartmentContact(Base):
    __tablename__ = "department_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String(50), nullable=False, index=True)  # ERP, MMS, MES, WMS, QMS, TMS, PLM, CUSTOMER_SERVICE
    role_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class DepartmentMapping(Base):
    __tablename__ = "department_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_category = Column(String(100), unique=True, nullable=False, index=True)
    issue_label = Column(String(150), nullable=False)
    responsible_department = Column(String(50), nullable=False, index=True)  # ERP, MMS, MES, WMS, QMS, TMS, PLM
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class SchedulerLease(Base):
    __tablename__ = "scheduler_leases"

    lease_name = Column(String(100), primary_key=True)
    holder_id = Column(String(150), nullable=True)
    acquired_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    last_heartbeat = Column(DateTime, nullable=True)
    last_cycle_status = Column(String(50), nullable=True)
    last_cycle_summary = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("risk_alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_order_id = Column(String(50), nullable=False, index=True)
    action_type = Column(String(50), nullable=False, index=True)  # REQUEST_EXPEDITE, NOTIFY_CUSTOMER_REVISED_DATE, REQUEST_CARRIER_UPGRADE, REQUEST_REASSESSMENT
    parameters = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="PROPOSED", index=True)  # PROPOSED, APPROVED, EXECUTED, REJECTED, FAILED
    requires_approval = Column(Boolean, nullable=False, default=True)
    proposed_by = Column(String(50), nullable=False, default="agent3-monitoring")
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    executed_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    alert = relationship("RiskAlert", backref="actions")
    approver = relationship("User", foreign_keys=[approved_by])


class AgentOutcome(Base):
    __tablename__ = "agent_outcomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_order_id = Column(String(50), nullable=False, index=True)
    proposal_id = Column(Integer, ForeignKey("commitment_proposals.id", ondelete="SET NULL"), nullable=True, index=True)
    promised_date = Column(Date, nullable=False, index=True)
    actual_delivery_date = Column(Date, nullable=False, index=True)
    variance_days = Column(Integer, nullable=False)  # actual - promised: <= 0 on-time, > 0 late
    approval_type = Column(String(50), nullable=False, index=True)  # AUTO_APPROVED | HUMAN_APPROVED
    commitment_met = Column(Boolean, nullable=False, index=True)  # True if variance_days <= 0 else False
    delivered_at = Column(DateTime, nullable=False, default=utcnow)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    proposal = relationship("CommitmentProposal")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(50), nullable=False, index=True)  # agent2 | agent3
    customer_order_id = Column(String(50), nullable=False, index=True)
    assessment_id = Column(String(50), nullable=True, index=True)
    alert_id = Column(Integer, nullable=True, index=True)
    status = Column(String(50), nullable=False, index=True)  # success | validation_failed_twice | error | rate_limit_paused | cost_limit_reached
    provider = Column(String(50), nullable=False, default="domo_ai")
    steps = Column(JSON, nullable=True)
    final_output = Column(JSON, nullable=True)
    llm_calls = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)






