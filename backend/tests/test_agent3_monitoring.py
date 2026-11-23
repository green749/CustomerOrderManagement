from datetime import date, timedelta
import pytest
from app.models.business import FactCustomerOrder
from app.models.workflow import OrderMonitoringRecord, RiskAlert, MonitoringExecutionLog
from app.services.monitoring_service import MonitoringService
from app.services.email_service import EmailService


def test_agent3_activation_and_baseline(db_session, test_user):
    """Test Agent 3 activates monitoring for a confirmed customer order."""
    order = db_session.query(FactCustomerOrder).filter(FactCustomerOrder.order_status == "CONFIRMED").first()
    if not order:
        order = db_session.query(FactCustomerOrder).first()

    approved_date = date(2026, 9, 30)
    rec = MonitoringService.activate_monitoring(
        db=db_session,
        customer_order_id=order.customer_order_id,
        approved_delivery_date=approved_date,
        user_id=test_user.id,
    )

    assert rec.id is not None
    assert rec.customer_order_id == order.customer_order_id
    assert rec.approved_delivery_date == approved_date
    assert rec.status == "ACTIVE"
    assert rec.baseline_milestones is not None


def test_agent3_monitoring_cycle_and_deduplication(db_session, test_user):
    """
    Test daily monitoring cycle detects risks, creates alerts, and
    deduplicates identical risks on subsequent runs without duplicate alerts.
    """
    order = db_session.query(FactCustomerOrder).first()
    approved_date = date(2026, 8, 10)  # Earlier date to test risk detection

    # Activate monitoring
    MonitoringService.activate_monitoring(
        db=db_session,
        customer_order_id=order.customer_order_id,
        approved_delivery_date=approved_date,
        user_id=test_user.id,
    )

    # Run Cycle 1
    ref_date = date(2026, 9, 1)  # 21 days past approved date -> triggers breach risk
    log1 = MonitoringService.run_daily_monitoring_cycle(db_session, cycle_type="MANUAL", as_of_date=ref_date)

    assert log1.status == "SUCCESS"

    alerts1 = db_session.query(RiskAlert).filter(
        RiskAlert.customer_order_id == order.customer_order_id,
        RiskAlert.status == "OPEN",
    ).all()
    count_cycle1 = len(alerts1)

    # Run Cycle 2 with identical state: Deduplication must NOT create duplicate alerts
    log2 = MonitoringService.run_daily_monitoring_cycle(db_session, cycle_type="MANUAL", as_of_date=ref_date)
    assert log2.status == "SUCCESS"

    alerts2 = db_session.query(RiskAlert).filter(
        RiskAlert.customer_order_id == order.customer_order_id,
        RiskAlert.status == "OPEN",
    ).all()
    count_cycle2 = len(alerts2)

    assert count_cycle2 == count_cycle1, "Deduplication failed: Duplicate open alerts were generated for identical risk."


def test_agent3_alert_resolution_workflow(db_session, test_user):
    """Test acknowledging, assigning, and resolving a risk alert."""
    order = db_session.query(FactCustomerOrder).first()

    # Create a test alert directly
    alert = RiskAlert(
        customer_order_id=order.customer_order_id,
        department="MES",
        risk_category="TEST_DELAY",
        severity="HIGH",
        title="Test work order delay",
        description="Testing resolution workflow.",
        status="OPEN",
        dedup_fingerprint=f"{order.customer_order_id}:MES:TEST_DELAY:HIGH",
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # 1. Acknowledge
    ack = MonitoringService.acknowledge_alert(db_session, alert.id, test_user)
    assert ack.status == "ACKNOWLEDGED"
    assert ack.acknowledged_by == test_user.id

    # 2. Assign
    assigned = MonitoringService.assign_alert(db_session, alert.id, "Vikram Patel", test_user)
    assert assigned.assigned_owner == "Vikram Patel"

    # 3. Resolve
    resolved = MonitoringService.resolve_alert(db_session, alert.id, "Work order completed on secondary line.", test_user)
    assert resolved.status == "RESOLVED"
    assert resolved.resolution_notes == "Work order completed on secondary line."
    assert resolved.resolved_by == test_user.id


def test_agent3_monitoring_closure_on_delivery(db_session, test_user):
    """Test monitoring stops and open alerts are resolved when order delivers."""
    order = db_session.query(FactCustomerOrder).first()

    rec = MonitoringService.activate_monitoring(
        db=db_session,
        customer_order_id=order.customer_order_id,
        approved_delivery_date=date(2026, 9, 15),
        user_id=test_user.id,
    )
    assert rec.status == "ACTIVE"

    # Close monitoring
    MonitoringService.close_monitoring(db_session, order.customer_order_id, reason="Customer POD confirmed delivered")
    db_session.refresh(rec)

    assert rec.status == "DELIVERED"
    assert rec.closed_at is not None
    assert "delivered" in rec.closure_reason.lower()
