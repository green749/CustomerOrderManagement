from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.models.business import DimCustomer, DimProduct, DimPlant, FactCustomerOrder
from app.models.workflow import (
    OrderAssessment,
    DepartmentReadiness,
    CommitmentProposal,
    OrderMonitoringRecord,
    MonitoringExecutionLog,
    RiskAlert,
    EmailNotificationLog,
    AuditLog,
)
from app.services.feasibility_service import FeasibilityService
from app.services.workflow_service import WorkflowService
from app.services.monitoring_service import MonitoringService
from app.services.email_service import EmailService


def test_complete_three_agent_lifecycle(db_session, test_user, test_manager):
    """
    MASTER INTEGRATION TEST: Full End-to-End Three-Agent Business Lifecycle:
    New Customer Order
    -> Agent 2 Assessment (7 departments readiness & achievable date)
    -> Commitment proposal created in PENDING
    -> Customer service manager reviews & approves
    -> Order commitment confirmed
    -> Agent 3 Monitoring automatically activates
    -> Daily monitoring cycle executes
    -> Risk alert created & email notification recorded
    -> Deduplication check (re-run does not duplicate alerts)
    -> Alert acknowledged, owner assigned, resolution documented
    -> Order delivery confirmed -> Agent 3 monitoring closes cleanly
    -> Complete audit history verified.
    """
    ref_date = date(2026, 8, 1)
    requested_date = ref_date + timedelta(days=20)

    # --------------------------------------------------------------------------
    # STAGE 1: AGENT 2 ASSESSMENT & INTAKE
    # --------------------------------------------------------------------------
    assessment = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=250,
        requested_delivery_date=requested_date,
        user=test_user,
        unit_price_inr=19500.0,
        priority="HIGH",
        channel="EDI",
        ship_to="Retailer Hub North, New Delhi",
        submit_for_approval=True,
        as_of_date=ref_date,
    )

    assert assessment.id is not None
    assert assessment.assessment_id.startswith("ASM-")
    assert assessment.overall_status in ["FEASIBLE", "FEASIBLE_WITH_RISKS"]
    assert assessment.estimated_delivery_date is not None
    assert assessment.proposal_id is not None

    # Check 7 departments
    dept_records = assessment.readiness_records
    assert len(dept_records) == 7
    dept_names = {d.department for d in dept_records}
    assert dept_names == {"ERP", "MMS", "MES", "WMS", "QMS", "TMS", "PLM"}

    # --------------------------------------------------------------------------
    # STAGE 2: COMMITMENT PROPOSAL IN PENDING (AGENTS CANNOT APPROVE)
    # --------------------------------------------------------------------------
    proposal = db_session.query(CommitmentProposal).filter(CommitmentProposal.id == assessment.proposal_id).first()
    assert proposal is not None
    assert proposal.status == "PENDING"
    assert proposal.decided_by is None
    assert proposal.decided_at is None

    # Verify audit log for proposal creation
    prop_audit = db_session.query(AuditLog).filter(
        AuditLog.action == "CREATE_FEASIBILITY_PROPOSAL",
        AuditLog.entity_id == assessment.assessment_id,
    ).first()
    assert prop_audit is not None

    # --------------------------------------------------------------------------
    # STAGE 3: CUSTOMER SERVICE MANAGER REVIEW & APPROVAL
    # --------------------------------------------------------------------------
    approved_prop = WorkflowService.approve_proposal(
        db=db_session,
        proposal_id=proposal.id,
        user=test_manager,
        decision_note="Commercial terms validated with customer. Delivery schedule approved.",
    )
    assert approved_prop.status == "APPROVED"
    assert approved_prop.decided_by == test_manager.id
    assert approved_prop.decided_at is not None

    # Verify audit log for approval
    appr_audit = db_session.query(AuditLog).filter(
        AuditLog.action == "APPROVE_PROPOSAL",
        AuditLog.entity_id == str(approved_prop.id),
    ).first()
    assert appr_audit is not None

    # --------------------------------------------------------------------------
    # STAGE 4: AGENT 3 MONITORING ACTIVATION
    # --------------------------------------------------------------------------
    monitoring_rec = db_session.query(OrderMonitoringRecord).filter(
        OrderMonitoringRecord.customer_order_id == approved_prop.customer_order_id
    ).first()
    assert monitoring_rec is not None
    assert monitoring_rec.status == "ACTIVE"
    assert monitoring_rec.approved_delivery_date == approved_prop.proposed_date
    assert monitoring_rec.started_at is not None

    # --------------------------------------------------------------------------
    # STAGE 5: AGENT 3 DAILY MONITORING RUN & RISK DETECTION
    # --------------------------------------------------------------------------
    # Run cycle with reference date past approved delivery to trigger breached risk
    future_date = approved_prop.proposed_date + timedelta(days=5)
    exec_log = MonitoringService.run_daily_monitoring_cycle(
        db=db_session,
        cycle_type="SCHEDULED",
        as_of_date=future_date,
    )
    assert exec_log.status == "SUCCESS", f"Execution log failed/skipped: {exec_log.summary}"
    assert exec_log.risks_found_count > 0

    # Verify alert was created
    alert = db_session.query(RiskAlert).filter(
        RiskAlert.customer_order_id == approved_prop.customer_order_id,
        RiskAlert.status == "OPEN",
    ).first()
    assert alert is not None
    assert alert.severity in ["CRITICAL", "HIGH", "MEDIUM"]
    assert alert.title is not None
    assert alert.description is not None

    # Verify email notification was recorded in email_notification_logs
    notif = db_session.query(EmailNotificationLog).filter(
        EmailNotificationLog.alert_id == alert.id
    ).first()
    assert notif is not None
    assert notif.recipient_email is not None
    assert notif.subject is not None
    assert notif.status in ["SENT", "PENDING_CONFIG", "FAILED"]

    # --------------------------------------------------------------------------
    # STAGE 6: DEDUPLICATION GUARANTEE
    # --------------------------------------------------------------------------
    initial_alert_count = db_session.query(RiskAlert).filter(
        RiskAlert.customer_order_id == approved_prop.customer_order_id
    ).count()

    # Re-run cycle with same date: must NOT create duplicate alerts
    exec_log2 = MonitoringService.run_daily_monitoring_cycle(
        db=db_session,
        cycle_type="SCHEDULED",
        as_of_date=future_date,
    )
    assert exec_log2.status == "SUCCESS"

    new_alert_count = db_session.query(RiskAlert).filter(
        RiskAlert.customer_order_id == approved_prop.customer_order_id
    ).count()
    assert new_alert_count == initial_alert_count, "Deduplication failed: Repeated daily cycle generated duplicate alerts."

    # --------------------------------------------------------------------------
    # STAGE 7: RISK RESOLUTION WORKFLOW
    # --------------------------------------------------------------------------
    # 1. Acknowledge
    ack_alert = MonitoringService.acknowledge_alert(db_session, alert.id, test_user)
    assert ack_alert.status == "ACKNOWLEDGED"

    # 2. Assign owner
    assign_alert = MonitoringService.assign_alert(db_session, alert.id, "Operations Lead", test_user)
    assert assign_alert.assigned_owner == "Operations Lead"

    # 3. Resolve
    resolve_alert = MonitoringService.resolve_alert(
        db_session,
        alert.id,
        resolution_notes="Customer agreed to expedited split shipment dispatch.",
        user=test_manager,
    )
    assert resolve_alert.status == "RESOLVED"
    assert resolve_alert.resolved_by == test_manager.id

    # --------------------------------------------------------------------------
    # STAGE 8: ORDER DELIVERY & MONITORING CLOSURE
    # --------------------------------------------------------------------------
    MonitoringService.close_monitoring(
        db_session,
        approved_prop.customer_order_id,
        reason="POD electronic proof of delivery verified",
    )

    db_session.refresh(monitoring_rec)
    assert monitoring_rec.status == "DELIVERED"
    assert monitoring_rec.closed_at is not None
    assert "deliver" in monitoring_rec.closure_reason.lower()
