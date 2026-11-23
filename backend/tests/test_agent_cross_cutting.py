import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.config import settings
from app.models.auth import User
from app.models.business import DimCustomer, FactCustomerOrder, FactShipmentMilestone
from app.models.workflow import (
    RiskAlert,
    OrderMonitoringRecord,
    CommitmentProposal,
    OrderAssessment,
    AgentAction,
    AgentOutcome,
    AuditLog,
    EmailNotificationLog,
)
from app.services.agent_controls_service import AgentControlsService
from app.services.approval_policy_service import (
    ApprovalPolicyService,
    pause_agent,
    resume_agent,
    is_agent_paused,
    get_or_create_policy_engine_user,
)
from app.services.feasibility_service import FeasibilityService
from app.services.monitoring_service import MonitoringService
from app.services.outcome_service import OutcomeService
from app.services.kpi_service import KPIService


def utcnow():
    return datetime.now(timezone.utc)


def test_confidence_low_escalates_to_needs_human_and_notifies_cs(db_session, test_user, monkeypatch):
    """
    Requirement 1:
    If an agent result has confidence LOW, mark the item NEEDS_HUMAN and notify
    the customer service contact via EmailService instead of acting.
    """
    monkeypatch.setenv("AUTO_APPROVE_ENABLED", "true")
    resume_agent("policy-engine")

    # Count CS emails before
    cs_emails_before = db_session.query(EmailNotificationLog).filter(
        EmailNotificationLog.recipient_category == "CUSTOMER_SERVICE"
    ).count()

    order = db_session.query(FactCustomerOrder).first()
    order_id = order.customer_order_id
    ref_date = date(2026, 8, 1)

    # 1. Create an assessment with confidence_level = "LOW"
    assessment = OrderAssessment(
        assessment_id=f"TEST-ASM-LOWCONF-{datetime.now().timestamp()}",
        customer_id=order.customer_id,
        product_id=order.product_id,
        order_qty=20,
        requested_delivery_date=ref_date + timedelta(days=20),
        overall_status="FEASIBLE",
        estimated_delivery_date=ref_date + timedelta(days=15),
        days_variance=-5,
        confidence_level="LOW",  # LOW CONFIDENCE
        blockers_summary=[],
        corrective_actions_summary=[],
        missing_data=[],
        customer_order_id=order_id,
        created_by=test_user.id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(assessment)
    db_session.flush()

    proposal = CommitmentProposal(
        customer_order_id=order_id,
        proposed_date=ref_date + timedelta(days=15),
        recommended_by="agent",
        reasons=["Assessment completed with low confidence"],
        status="PENDING",
        created_by=test_user.id,
        revision=1,
        created_at=utcnow(),
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(assessment)
    db_session.refresh(proposal)

    customer = db_session.query(DimCustomer).filter(DimCustomer.customer_id == order.customer_id).first()

    # 2. Evaluate policy: must return NEEDS_HUMAN due to confidence LOW
    eval_result = ApprovalPolicyService.evaluate_and_apply(
        proposal=proposal,
        assessment=assessment,
        customer=customer,
        db=db_session,
    )

    assert eval_result["decision"] == "NEEDS_HUMAN"
    assert proposal.status == "PENDING"  # NOT auto-approved!
    assert any("confidence" in r.lower() for r in eval_result["reasons"])

    # 3. Verify notification dispatched to Customer Service contact
    cs_emails_after = db_session.query(EmailNotificationLog).filter(
        EmailNotificationLog.recipient_category == "CUSTOMER_SERVICE"
    ).count()
    assert cs_emails_after > cs_emails_before

    # 4. Verify audit log contains reasoning
    escalate_audit = db_session.query(AuditLog).filter(
        AuditLog.action.in_(["POLICY_ESCALATE", "AGENT_ESCALATION"]),
        AuditLog.entity_id.in_([str(proposal.id), order_id]),
    ).first()
    assert escalate_audit is not None
    assert "NEEDS_HUMAN" in str(escalate_audit.payload)


def test_validation_failure_twice_escalates_to_needs_human(db_session, monkeypatch):
    """
    Requirement 1:
    If LLM output fails validation twice, mark item NEEDS_HUMAN and notify CS.
    """
    order = db_session.query(FactCustomerOrder).first()
    order_id = f"{order.customer_order_id}-VALTEST"

    emails_before = db_session.query(EmailNotificationLog).filter(
        EmailNotificationLog.recipient_category == "CUSTOMER_SERVICE"
    ).count()

    # Trigger escalation directly through AgentControlsService
    AgentControlsService.escalate_item(
        db=db_session,
        customer_order_id=order_id,
        reason="LLM output failed validation twice during feasibility evaluation",
        agent_name="agent2",
        details={"attempts": 2, "validation_error": "Invalid JSON root structure"},
    )

    emails_after = db_session.query(EmailNotificationLog).filter(
        EmailNotificationLog.recipient_category == "CUSTOMER_SERVICE"
    ).count()
    assert emails_after > emails_before

    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "AGENT_ESCALATION",
        AuditLog.entity_id == order_id,
    ).order_by(AuditLog.id.desc()).first()
    assert audit_entry is not None
    assert "validation twice" in audit_entry.payload["reason"]


def test_hourly_llm_limit_pauses_agent_and_raises_admin_alert(db_session, monkeypatch):
    """
    Requirement 2:
    Central setting for max LLM calls per hour.
    When hit, pause that agent and raise an admin alert.
    """
    monkeypatch.setenv("MAX_LLM_CALLS_PER_HOUR", "3")
    resume_agent("agent2")
    assert not is_agent_paused("agent2")

    # Record 3 LLM calls for agent2
    AgentControlsService.record_llm_call("agent2", count=3)

    # Check and enforce
    allowed = AgentControlsService.check_and_enforce_llm_call_limit(db_session, "agent2")
    assert allowed is False  # Limit exceeded

    # Verify agent2 is PAUSED
    assert is_agent_paused("agent2") is True

    # Verify admin alert raised in risk_alerts
    admin_alert = db_session.query(RiskAlert).filter(
        RiskAlert.department == "ADMIN",
        RiskAlert.risk_category == "LIMIT_EXCEEDED",
        RiskAlert.status == "OPEN",
    ).first()
    assert admin_alert is not None
    assert "MAX_LLM_CALLS_PER_HOUR" in admin_alert.title
    assert admin_alert.severity == "CRITICAL"

    # Verify admin email dispatched
    admin_email = db_session.query(EmailNotificationLog).filter(
        EmailNotificationLog.department == "ADMIN",
        EmailNotificationLog.recipient_category == "OPERATIONAL",
    ).first()
    assert admin_email is not None

    # Verify audit log
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "ADMIN_ALERT_RAISED",
        AuditLog.entity_id == "agent2",
    ).first()
    assert audit_log is not None


def test_daily_auto_actions_limit_pauses_agent(db_session, monkeypatch):
    """
    Requirement 2:
    Max auto-actions per day governor limit.
    """
    order = db_session.query(FactCustomerOrder).first()
    resume_agent("agent3")

    # Create 2 actions
    AgentActionRepository = None
    from app.repositories.agent_action_repo import AgentActionRepository
    action1 = AgentActionRepository.create_action(
        db=db_session,
        customer_order_id=order.customer_order_id,
        action_type="REQUEST_EXPEDITE",
        status="EXECUTED",
    )
    action2 = AgentActionRepository.create_action(
        db=db_session,
        customer_order_id=order.customer_order_id,
        action_type="REQUEST_CARRIER_UPGRADE",
        status="EXECUTED",
    )

    # Set governor limit to 2
    monkeypatch.setenv("MAX_AUTO_ACTIONS_PER_DAY", "2")

    allowed = AgentControlsService.check_and_enforce_auto_actions_limit(db_session, "agent3")
    assert allowed is False
    assert is_agent_paused("agent3") is True


def test_cycle_cost_limit_pauses_agent(db_session, monkeypatch):
    """
    Requirement 2:
    Max cost per cycle governor limit.
    """
    monkeypatch.setenv("MAX_COST_PER_CYCLE", "2.0")
    resume_agent("agent3")

    # Enforce cost exceeding limit ($3.50 > $2.00)
    allowed = AgentControlsService.check_and_enforce_cycle_cost_limit(db_session, "agent3", cycle_cost=3.50)
    assert allowed is False
    assert is_agent_paused("agent3") is True


def test_outcome_tracking_when_monitoring_closes_delivered(db_session, test_user):
    """
    Requirement 4:
    New table agent_outcomes recording, per approved order, the promised date
    and the actual delivery date. When monitoring closes an order as DELIVERED,
    store the variance and whether an auto-approved or human-approved commitment was met.
    """
    order = db_session.query(FactCustomerOrder).first()
    order_id = order.customer_order_id
    ref_date = date(2026, 8, 1)
    promised = ref_date + timedelta(days=10)

    # Clean up prior test runs
    db_session.query(AgentOutcome).filter(AgentOutcome.customer_order_id == order_id).delete()
    db_session.commit()

    # Create an approved proposal for this order
    policy_user = get_or_create_policy_engine_user(db_session)
    proposal = CommitmentProposal(
        customer_order_id=order_id,
        proposed_date=promised,
        recommended_by="agent",
        status="APPROVED",
        decision_note="Auto-approved by policy engine",
        decided_by=policy_user.id,
        decided_at=utcnow(),
        created_by=test_user.id,
        revision=1,
        created_at=utcnow(),
    )
    db_session.add(proposal)

    # Ensure active monitoring record
    mon_rec = db_session.query(OrderMonitoringRecord).filter(
        OrderMonitoringRecord.customer_order_id == order_id
    ).first()
    if not mon_rec:
        mon_rec = OrderMonitoringRecord(
            customer_order_id=order_id,
            approved_delivery_date=promised,
            status="ACTIVE",
            started_at=utcnow(),
            created_at=utcnow(),
        )
        db_session.add(mon_rec)
    else:
        mon_rec.status = "ACTIVE"
        mon_rec.approved_delivery_date = promised
    db_session.commit()

    # Close monitoring with DELIVERED status
    MonitoringService.close_monitoring(db_session, order_id, reason="Order successfully delivered.")

    # Verify agent_outcomes has a record
    outcome = (
        db_session.query(AgentOutcome)
        .filter(AgentOutcome.customer_order_id == order_id)
        .order_by(AgentOutcome.id.desc())
        .first()
    )
    assert outcome is not None
    assert outcome.promised_date == promised
    assert outcome.actual_delivery_date is not None
    assert outcome.approval_type in ["HUMAN_APPROVED", "AUTO_APPROVED"]
    assert isinstance(outcome.variance_days, int)
    assert isinstance(outcome.commitment_met, bool)

    # Verify audit log recorded
    outcome_audit = db_session.query(AuditLog).filter(
        AuditLog.action == "RECORD_OUTCOME",
        AuditLog.entity_id == str(outcome.id),
    ).first()
    assert outcome_audit is not None


def test_kpi_endpoint_returns_governance_metrics(client, auth_headers, db_session):
    """
    Requirement 5:
    KPI endpoint returns:
    - on-time rate for auto-approved vs human-approved
    - number of agent escalations
    - average alert-to-resolution time
    """
    resp = client.get("/api/kpis/agent-performance", headers=auth_headers)
    assert resp.status_code == 200
    kpi_data = resp.json()

    assert "auto_approved_on_time_rate" in kpi_data
    assert "human_approved_on_time_rate" in kpi_data
    assert "total_escalations" in kpi_data
    assert "avg_alert_resolution_hours" in kpi_data
    assert isinstance(kpi_data["auto_approved_on_time_rate"], (int, float))
    assert isinstance(kpi_data["total_escalations"], int)


def test_admin_agent_control_overview_and_kill_switch_api(client, auth_headers, db_session):
    """
    Requirement 3:
    Admin agent overview endpoint and pause/resume buttons backing.
    """
    # 1. GET /api/admin/agents/overview
    resp = client.get("/api/admin/agents/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "agents" in data
    assert "limits" in data
    assert "counts" in data

    agent_ids = [a["id"] for a in data["agents"]]
    assert "agent1" in agent_ids
    assert "agent2" in agent_ids
    assert "agent3" in agent_ids
    assert "policy-engine" in agent_ids

    # 2. Pause agent3 via endpoint
    pause_resp = client.post(
        "/api/admin/agents/agent3/pause",
        json={"reason": "Manual operator pause for maintenance"},
        headers=auth_headers,
    )
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "PAUSED"

    # Verify overview reflects paused status
    resp2 = client.get("/api/admin/agents/overview", headers=auth_headers)
    a3 = next(a for a in resp2.json()["agents"] if a["id"] == "agent3")
    assert a3["status"] == "PAUSED"

    # 3. Resume agent3 via endpoint
    resume_resp = client.post(
        "/api/admin/agents/agent3/resume",
        headers=auth_headers,
    )
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "ACTIVE"
