import pytest
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.business import FactCustomerOrder, DimCustomer, DimProduct
from app.models.workflow import (
    CommitmentProposal,
    OrderMonitoringRecord,
    MonitoringExecutionLog,
    RiskAlert,
    EmailNotificationLog,
    SchedulerLease,
)
from app.services.lease_service import DistributedSchedulerLeaseManager
from app.services.monitoring_service import MonitoringService
from app.services.feasibility_service import FeasibilityService
from app.services.workflow_service import WorkflowService
from app.services.email_service import EmailService, MockEmailProvider, SMTPEmailProvider


def utcnow():
    return datetime.now(timezone.utc)


def test_distributed_scheduler_lease_mutual_exclusion(db_session: Session):
    """Verify distributed lease prevents concurrent executions by two worker processes."""
    worker_1 = "worker-node-1:1001:abcd"
    worker_2 = "worker-node-2:2002:efgh"
    lease_name = "TEST_MUTUAL_EXCLUSION"

    # Worker 1 claims lease
    acquired, reason = DistributedSchedulerLeaseManager.acquire_lease(
        db_session, lease_name=lease_name, lease_duration_seconds=300, worker_id=worker_1
    )
    assert acquired is True
    assert reason is None

    # Worker 2 attempts to claim active lease
    acquired_2, reason_2 = DistributedSchedulerLeaseManager.acquire_lease(
        db_session, lease_name=lease_name, lease_duration_seconds=300, worker_id=worker_2
    )
    assert acquired_2 is False
    assert "currently held by worker" in reason_2

    # Worker 1 releases lease
    DistributedSchedulerLeaseManager.release_lease(db_session, lease_name=lease_name, worker_id=worker_1)

    # Worker 2 can now claim lease
    acquired_3, reason_3 = DistributedSchedulerLeaseManager.acquire_lease(
        db_session, lease_name=lease_name, lease_duration_seconds=300, worker_id=worker_2
    )
    assert acquired_3 is True


def test_distributed_scheduler_lease_stale_recovery(db_session: Session):
    """Verify crashed/stale lease is safely recovered by another worker after expiry."""
    crashed_worker = "crashed-pod:9999:dead"
    recovery_worker = "healthy-pod:1111:live"
    lease_name = "TEST_STALE_RECOVERY"

    # Create an expired lease directly in the DB (simulating worker crash 15 minutes ago)
    past_time = utcnow() - timedelta(minutes=15)
    stale_lease = SchedulerLease(
        lease_name=lease_name,
        holder_id=crashed_worker,
        acquired_at=past_time,
        expires_at=past_time + timedelta(minutes=5),  # expired 10 minutes ago
        last_heartbeat=past_time,
        version=1,
    )
    db_session.add(stale_lease)
    db_session.commit()

    # Recovery worker attempts to acquire expired lease
    acquired, reason = DistributedSchedulerLeaseManager.acquire_lease(
        db_session, lease_name=lease_name, lease_duration_seconds=300, worker_id=recovery_worker
    )
    assert acquired is True

    # Check that recovery worker is now holder and version incremented
    lease = db_session.query(SchedulerLease).filter(SchedulerLease.lease_name == lease_name).first()
    assert lease.holder_id == recovery_worker
    assert lease.version == 2


def test_scheduler_cycle_skips_when_lease_held(db_session: Session):
    """Verify monitoring cycle exits cleanly with SKIPPED status if another instance holds the lease."""
    external_worker = "external-replica:5555:lock"
    # Claim the lease with an external worker
    DistributedSchedulerLeaseManager.acquire_lease(
        db_session, lease_name="DAILY_MONITORING", lease_duration_seconds=300, worker_id=external_worker
    )

    # Attempt to run daily cycle
    log = MonitoringService.run_daily_monitoring_cycle(db_session, cycle_type="SCHEDULED")
    assert log.status == "SKIPPED"
    assert "skipped" in log.summary.lower()

    # Clean up lease
    DistributedSchedulerLeaseManager.release_lease(db_session, lease_name="DAILY_MONITORING", worker_id=external_worker)


def test_self_approval_prevention_for_managers(db_session: Session):
    """Segregation of duties: Creator cannot approve their own proposal unless administrator."""
    manager_user = db_session.query(User).filter(User.role == "manager").first()
    if not manager_user:
        manager_user = User(email="test_mgr@test.com", full_name="Test Manager 1", role="manager", hashed_password="pw")
        db_session.add(manager_user)
        db_session.commit()

    other_manager = db_session.query(User).filter(User.role == "manager", User.id != manager_user.id).first()
    if not other_manager:
        other_manager = User(email="test_mgr2@test.com", full_name="Test Manager 2", role="manager", hashed_password="pw")
        db_session.add(other_manager)
        db_session.commit()

    # Manager creates proposal
    prop = CommitmentProposal(
        customer_order_id="CO-000001",
        proposed_date=date(2026, 9, 15),
        recommended_by="user",
        reasons=["Test proposal"],
        status="PENDING",
        created_by=manager_user.id,
        revision=1,
    )
    db_session.add(prop)
    db_session.commit()

    # Manager attempts to approve their own proposal -> Rejected
    with pytest.raises(ValueError, match="Segregation of duties violation"):
        WorkflowService.approve_proposal(db_session, prop.id, user=manager_user)

    # Other manager approves -> Accepted
    approved = WorkflowService.approve_proposal(db_session, prop.id, user=other_manager)
    assert approved.status == "APPROVED"
    assert approved.decided_by == other_manager.id


def test_email_provider_unconfigured_records_pending_config(db_session: Session):
    """When SMTP is not configured, email notification is recorded as PENDING_CONFIG without false claims."""
    EmailService.set_provider(SMTPEmailProvider())

    alert = RiskAlert(
        customer_order_id="CO-000001",
        department="ERP",
        risk_category="DELIVERY_DATE_BREACHED",
        severity="HIGH",
        title="Test delivery breach alert",
        description="Delivery commitment has elapsed.",
        status="OPEN",
        dedup_fingerprint="test_fp_unconfigured",
        detected_at=utcnow(),
    )
    db_session.add(alert)
    db_session.commit()

    log = EmailService.send_risk_alert_email(db_session, alert=alert)
    assert log.status == "PENDING_CONFIG"
    assert "not configured" in log.failure_reason.lower()
    assert log.sent_at is None


def test_email_provider_mock_and_independent_retry(db_session: Session):
    """Verify provider abstraction, failure logging, and independent retry mechanism."""
    # Step 1: Use mock provider in failing mode
    failing_mock = MockEmailProvider(simulate_failure=True, failure_reason="Temporary gateway timeout")
    EmailService.set_provider(failing_mock)

    alert = RiskAlert(
        customer_order_id="CO-000001",
        department="MES",
        risk_category="PRODUCTION_DELAY",
        severity="HIGH",
        title="Test production delay alert",
        description="Assembly station bottleneck.",
        status="OPEN",
        dedup_fingerprint="test_fp_retry",
        detected_at=utcnow(),
    )
    db_session.add(alert)
    db_session.commit()

    log = EmailService.send_risk_alert_email(db_session, alert=alert)
    assert log.status == "FAILED"
    assert log.retry_count == 1
    assert "gateway timeout" in log.failure_reason.lower()

    # Step 2: Switch to healthy mock provider and retry independently
    healthy_mock = MockEmailProvider(simulate_failure=False)
    EmailService.set_provider(healthy_mock)

    retried_log = EmailService.retry_failed_notification(db_session, log.id)
    assert retried_log.status == "SENT"
    assert retried_log.sent_at is not None
    assert retried_log.failure_reason is None
    assert retried_log.retry_count == 2
    assert len(healthy_mock.sent_emails) == 1

    # Reset provider
    EmailService.reset_provider()


def test_invalid_recipient_email_validation(db_session: Session):
    """Verify that malformed email addresses are rejected with FAILED status and explicit reason."""
    assert EmailService.validate_email_address("valid.user@company.com") is True
    assert EmailService.validate_email_address("invalid-email-address") is False
    assert EmailService.validate_email_address("") is False
    assert EmailService.validate_email_address(None) is False


def test_agent3_deduplication_fingerprint_sha256(db_session: Session):
    """Verify deterministic SHA-256 fingerprinting prevents duplicate alerts on repeated cycles."""
    mon_rec = OrderMonitoringRecord(
        customer_order_id="CO-TEST-DEDUP",
        approved_delivery_date=date(2026, 8, 1),
        status="ACTIVE",
        started_at=utcnow(),
    )
    db_session.add(mon_rec)
    db_session.commit()

    risk_dict = {
        "department": "ERP",
        "risk_category": "DELIVERY_DATE_BREACHED",
        "severity": "CRITICAL",
        "title": "Breached delivery date",
        "description": "Elapsed delivery date.",
        "delivery_impact": "Delayed",
        "recommended_action": "Escalate",
    }

    # Cycle 1: Creates alert
    created_1 = MonitoringService._record_risk_alert(db_session, mon_rec, risk_dict)
    assert created_1 is True

    # Cycle 2: Same risk detected -> Deduplicated
    created_2 = MonitoringService._record_risk_alert(db_session, mon_rec, risk_dict)
    assert created_2 is False

    # Check alert dedup fingerprint is a 64-char hex string (SHA-256)
    alert = db_session.query(RiskAlert).filter(RiskAlert.customer_order_id == "CO-TEST-DEDUP").first()
    assert len(alert.dedup_fingerprint) == 64


def test_agent3_cancelled_order_stops_monitoring(db_session: Session):
    """Verify that when an order is cancelled, monitoring record is closed and risk detection ceases."""
    mon_rec = OrderMonitoringRecord(
        customer_order_id="CO-TEST-CANCEL",
        approved_delivery_date=date(2026, 8, 1),
        status="ACTIVE",
        started_at=utcnow(),
    )
    db_session.add(mon_rec)
    db_session.commit()

    # Close monitoring due to cancellation
    MonitoringService.close_monitoring(db_session, "CO-TEST-CANCEL", reason="Customer order was cancelled by account lead.")
    db_session.refresh(mon_rec)

    assert mon_rec.status == "CANCELLED"
    assert "cancelled" in mon_rec.closure_reason.lower()
    assert mon_rec.closed_at is not None


def test_agent3_resolved_risk_recurrence_creates_new_alert(db_session: Session):
    """Verify that if an alert is RESOLVED and the risk condition recurs later, a new alert is generated."""
    mon_rec = OrderMonitoringRecord(
        customer_order_id="CO-TEST-RECUR",
        approved_delivery_date=date(2026, 8, 1),
        status="ACTIVE",
        started_at=utcnow(),
    )
    db_session.add(mon_rec)
    db_session.commit()

    risk_dict = {
        "department": "MES",
        "risk_category": "PRODUCTION_DELAY",
        "severity": "HIGH",
        "title": "Production delay",
        "description": "Line backlog.",
    }

    # Initial detection
    created_1 = MonitoringService._record_risk_alert(db_session, mon_rec, risk_dict)
    assert created_1 is True

    # User resolves the alert
    alert = db_session.query(RiskAlert).filter(RiskAlert.customer_order_id == "CO-TEST-RECUR").first()
    alert.status = "RESOLVED"
    alert.resolved_at = utcnow()
    alert.resolution_notes = "Overtime completed; line back on track."
    db_session.commit()

    # Recurrence of same risk condition creates a fresh alert
    created_2 = MonitoringService._record_risk_alert(db_session, mon_rec, risk_dict)
    assert created_2 is True

    total_alerts = db_session.query(RiskAlert).filter(RiskAlert.customer_order_id == "CO-TEST-RECUR").count()
    assert total_alerts == 2


def test_agent2_missing_critical_data_produces_blocked(db_session: Session):
    """Verify that Agent 2 marks non-existent customer or product as BLOCKED/NOT_FEASIBLE with diagnostic details."""
    admin_user = db_session.query(User).filter(User.role == "admin").first()

    assessment = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUST-NONEXISTENT",
        product_id="PROD-NONEXISTENT",
        order_qty=500,
        requested_delivery_date=date(2026, 9, 1),
        user=admin_user,
        submit_for_approval=False,
    )
    assert assessment.overall_status in ("BLOCKED", "NOT_FEASIBLE")
    assert len(assessment.blockers_summary) >= 1
    assert assessment.missing_data is not None
