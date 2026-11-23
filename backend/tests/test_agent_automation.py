import os
from datetime import date, datetime, timedelta
import pytest

from app.models.business import FactCustomerOrder, FactProductionOrder, FactQualityInspection, FactShipmentMilestone
from app.models.workflow import OrderAssessment, RiskAlert, OrderMonitoringRecord, CommitmentProposal
from app.models.auth import User
from app.services.intake_service import BackgroundIntakeWatcher, get_or_create_system_user
from app.services.feasibility_service import FeasibilityService
from app.services.monitoring_service import MonitoringService, notify_order_changed
from app.services.scheduler_service import BackgroundMonitoringScheduler
from app.services.order_service import OrderService


def test_idempotent_intake(db_session):
    """
    Test that Agent 2 intake watcher:
    - Finds orders with status NEW or OPEN that have no assessment.
    - Evaluates feasibility with submit_for_approval=True and user agent2-system.
    - Is idempotent: Never creates duplicate assessments for the same order when polled repeatedly.
    """
    test_order_id = "CO-AUTO-INTAKE-001"
    
    # Ensure clean state
    db_session.query(CommitmentProposal).filter(CommitmentProposal.customer_order_id == test_order_id).delete()
    db_session.query(OrderAssessment).filter(OrderAssessment.customer_order_id == test_order_id).delete()
    db_session.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == test_order_id).delete()
    db_session.commit()

    # Create a fresh OPEN order
    order = FactCustomerOrder(
        customer_order_id=test_order_id,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_date=date(2026, 8, 1),
        requested_delivery_date=date(2026, 8, 25),
        confirmed_delivery_date=date(2026, 8, 25),
        order_qty=50,
        shipped_qty=0,
        unit_price_inr=15000.0,
        order_status="OPEN",
        priority="MEDIUM",
        channel="PORTAL",
    )
    db_session.add(order)
    db_session.commit()

    # Run intake poller cycle 1
    results_cycle_1 = BackgroundIntakeWatcher.poll_new_orders(
        db=db_session,
        force_lease=True,
        poll_interval_seconds=300,
        enabled=True,
    )

    created_for_order = [r for r in results_cycle_1 if r.customer_order_id == test_order_id]
    assert len(created_for_order) == 1
    asm1 = created_for_order[0]
    assert asm1.customer_order_id == test_order_id
    assert asm1.customer_id == "CUS-001"
    assert asm1.product_id == "SPH-A15-128"

    # Verify created_by matches agent2-system
    system_user = db_session.query(User).filter(User.id == asm1.created_by).first()
    assert system_user is not None
    assert "agent2-system" in system_user.email

    # Verify commitment proposal was created in PENDING status
    proposal = db_session.query(CommitmentProposal).filter(
        CommitmentProposal.customer_order_id == test_order_id
    ).first()
    assert proposal is not None
    assert proposal.status == "PENDING"
    assert proposal.created_by == system_user.id

    # Run intake poller cycle 2 (idempotency check via watcher)
    results_cycle_2 = BackgroundIntakeWatcher.poll_new_orders(
        db=db_session,
        force_lease=True,
        poll_interval_seconds=300,
        enabled=True,
    )
    duplicate_for_order = [r for r in results_cycle_2 if r.customer_order_id == test_order_id]
    assert len(duplicate_for_order) == 0

    # Direct FeasibilityService assess_new_order call with same customer_order_id (idempotency check)
    asm2 = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id=order.customer_id,
        product_id=order.product_id,
        order_qty=order.order_qty,
        requested_delivery_date=order.requested_delivery_date,
        user=system_user,
        submit_for_approval=True,
        customer_order_id=test_order_id,
    )
    assert asm2.id == asm1.id

    # Verify in DB that exactly ONE assessment exists for this order
    all_asms = db_session.query(OrderAssessment).filter(
        OrderAssessment.customer_order_id == test_order_id
    ).all()
    assert len(all_asms) == 1


def test_event_check_creates_no_duplicate_alert(db_session, test_user):
    """
    Test that Agent 3 event check:
    - Evaluates risks for a single order.
    - Records alerts with deduplication fingerprint.
    - Calling it multiple times on unchanged conditions does not create duplicate alerts.
    - Triggers properly via notify_order_changed and OrderService update helpers.
    """
    test_order_id = "CO-AUTO-MON-001"

    # Clean up prior test runs
    db_session.query(RiskAlert).filter(RiskAlert.customer_order_id == test_order_id).delete()
    db_session.query(OrderMonitoringRecord).filter(OrderMonitoringRecord.customer_order_id == test_order_id).delete()
    db_session.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == test_order_id).delete()
    db_session.commit()

    # Create an order where approved date is in the past relative to ref_date (triggering breach risk)
    order = FactCustomerOrder(
        customer_order_id=test_order_id,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_date=date(2026, 7, 1),
        requested_delivery_date=date(2026, 7, 20),
        confirmed_delivery_date=date(2026, 7, 20),
        order_qty=100,
        shipped_qty=0,
        unit_price_inr=15000.0,
        order_status="IN_PRODUCTION",
        priority="HIGH",
        channel="EDI",
    )
    db_session.add(order)
    db_session.commit()

    ref_date = date(2026, 8, 1)

    # 1. Run event check 1st time
    alerts_1 = MonitoringService.run_event_check(
        db=db_session,
        customer_order_id=test_order_id,
        as_of_date=ref_date,
    )
    assert len(alerts_1) >= 1
    initial_alert_count = len(alerts_1)

    # 2. Run event check 2nd time on identical conditions
    alerts_2 = MonitoringService.run_event_check(
        db=db_session,
        customer_order_id=test_order_id,
        as_of_date=ref_date,
    )
    assert len(alerts_2) == initial_alert_count

    # Verify no duplicate alert rows exist in database
    db_alerts = db_session.query(RiskAlert).filter(
        RiskAlert.customer_order_id == test_order_id
    ).all()
    assert len(db_alerts) == initial_alert_count

    # Check deduplication fingerprints are unique per category
    fingerprints = [a.dedup_fingerprint for a in db_alerts]
    assert len(fingerprints) == len(set(fingerprints))

    # 3. Test notify_order_changed helper
    alerts_3 = notify_order_changed(test_order_id, db=db_session)
    assert len(alerts_3) == initial_alert_count

    # 4. Test write path helper: update_shipment_status triggers event check
    # Create a test shipment milestone
    test_shipment_id = "SH-AUTO-001"
    db_session.query(FactShipmentMilestone).filter(FactShipmentMilestone.shipment_id == test_shipment_id).delete()
    db_session.commit()

    sm = FactShipmentMilestone(
        shipment_id=test_shipment_id,
        customer_order_id=test_order_id,
        plant_id="PLANT-001",
        warehouse_id="WH-001",
        carrier="BlueDart",
        vehicle_type="TRUCK_FTL",
        dispatch_date=date(2026, 7, 18),
        planned_eta=datetime(2026, 7, 20, 10, 0, 0),
        actual_delivery_ts=None,
        shipment_qty=100,
        freight_cost_inr=5000.0,
        vehicle_utilization_pct=85.0,
        pod_status="PENDING",
        shipment_status="IN_TRANSIT",
    )
    from app.models.business import enable_seed_mutation, disable_seed_mutation
    enable_seed_mutation()
    try:
        db_session.add(sm)
        db_session.commit()
    finally:
        disable_seed_mutation()

    updated_sm = OrderService.update_shipment_status(db_session, test_shipment_id, "DELAYED")
    assert updated_sm is not None
    assert updated_sm.shipment_status == "DELAYED"


def test_disabled_flags_do_nothing(db_session):
    """
    Test that disabled flags properly prevent background automation from running:
    - AGENT2_AUTONOMOUS_ENABLED = False returns [] and starts no thread.
    - INTAKE_POLL_SECONDS <= 0 returns [] and starts no thread.
    - MONITORING_INTERVAL_SECONDS <= 0 disables scheduler thread.
    """
    # 1. Intake poller disabled via enabled=False
    results_disabled = BackgroundIntakeWatcher.poll_new_orders(
        db=db_session,
        force_lease=True,
        enabled=False,
        poll_interval_seconds=300,
    )
    assert results_disabled == []

    # 2. Intake poller disabled via interval <= 0
    results_zero_interval = BackgroundIntakeWatcher.poll_new_orders(
        db=db_session,
        force_lease=True,
        enabled=True,
        poll_interval_seconds=0,
    )
    assert results_zero_interval == []

    # 3. BackgroundIntakeWatcher start() with enabled=False spawns no thread
    watcher_disabled = BackgroundIntakeWatcher(enabled=False, poll_interval_seconds=300)
    watcher_disabled.start()
    assert watcher_disabled._thread is None

    # 4. BackgroundIntakeWatcher start() with interval=0 spawns no thread
    watcher_interval_zero = BackgroundIntakeWatcher(enabled=True, poll_interval_seconds=0)
    watcher_interval_zero.start()
    assert watcher_interval_zero._thread is None

    # 5. BackgroundMonitoringScheduler start() with interval=0 spawns no thread
    scheduler_disabled = BackgroundMonitoringScheduler(interval_seconds=0)
    scheduler_disabled.start()
    assert scheduler_disabled._thread is None
