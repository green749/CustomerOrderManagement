import os
from datetime import date, datetime, timedelta, timezone
import pytest

from app.config import settings
from app.models.auth import User
from app.models.business import FactCustomerOrder, FactProductionOrder, FactInventoryDailySnapshot
from app.models.workflow import (
    RiskAlert,
    OrderMonitoringRecord,
    CommitmentProposal,
    AgentAction,
    AuditLog,
)
from app.repositories.agent_action_repo import AgentActionRepository
from app.repositories.commitment_repo import CommitmentRepository
from app.services.agent_action_service import AgentActionService
from app.services.monitoring_service import MonitoringService
from app.services.workflow_service import WorkflowService


def utcnow():
    return datetime.now(timezone.utc)


def _get_or_create_monitored_order(db_session):
    """Helper to get a real customer order and ensure active monitoring record exists."""
    order = db_session.query(FactCustomerOrder).first()
    assert order is not None, "At least one customer order must exist in seed"

    mon_rec = db_session.query(OrderMonitoringRecord).filter(
        OrderMonitoringRecord.customer_order_id == order.customer_order_id
    ).first()
    if not mon_rec:
        mon_rec = OrderMonitoringRecord(
            customer_order_id=order.customer_order_id,
            approved_delivery_date=order.requested_delivery_date or (date.today() + timedelta(days=14)),
            status="ACTIVE",
            started_at=utcnow(),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db_session.add(mon_rec)
        db_session.commit()
        db_session.refresh(mon_rec)
    return order, mon_rec


def test_action_lifecycle_and_rejection(db_session, test_user):
    """
    Test action lifecycle:
    1. PROPOSED with requires_approval=True
    2. Approval transitions to EXECUTED, writes audit log, dispatches email
    3. Rejection of another proposed action transitions to REJECTED with reason recorded
    """
    order, mon_rec = _get_or_create_monitored_order(db_session)

    # 1. Create a dummy risk alert
    alert = RiskAlert(
        customer_order_id=order.customer_order_id,
        monitoring_record_id=mon_rec.id,
        department="MES",
        risk_category="PRODUCTION_DELAY",
        severity="HIGH",
        title="Production line bottleneck",
        description="Machine spindle failure at Line 2",
        status="OPEN",
        dedup_fingerprint=f"lifecycle-test-{datetime.now().timestamp()}",
        detected_at=utcnow(),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # 2. Propose action
    action = AgentActionService.propose_action_for_risk(
        db=db_session,
        alert=alert,
        risk_dict={"risk_category": alert.risk_category, "department": alert.department, "title": alert.title},
    )
    assert action is not None
    assert action.status == "PROPOSED"
    assert action.action_type == "REQUEST_EXPEDITE"
    assert action.requires_approval is True
    assert action.proposed_by == "agent3-monitoring"
    assert action.executed_at is None

    # Check AuditLog for proposal
    prop_audit = db_session.query(AuditLog).filter(
        AuditLog.entity == "agent_action",
        AuditLog.entity_id == str(action.id),
        AuditLog.action == "PROPOSE_ACTION",
    ).first()
    assert prop_audit is not None

    # 3. Approve and execute
    executed_action = AgentActionService.approve_action(
        db=db_session,
        action_id=action.id,
        user=test_user,
    )
    assert executed_action.status == "EXECUTED"
    assert executed_action.approved_by == test_user.id
    assert executed_action.executed_at is not None
    assert executed_action.result is not None
    assert executed_action.result.get("status") == "SUCCESS"

    # Check AuditLog for approval and execution
    exec_audit = db_session.query(AuditLog).filter(
        AuditLog.entity == "agent_action",
        AuditLog.entity_id == str(action.id),
        AuditLog.action == "EXECUTE_ACTION",
    ).first()
    assert exec_audit is not None

    # 4. Rejection lifecycle test on a second alert
    alert2 = RiskAlert(
        customer_order_id=order.customer_order_id,
        monitoring_record_id=mon_rec.id,
        department="TMS",
        risk_category="SHIPMENT_EXCEPTION",
        severity="MEDIUM",
        title="Truck delayed at hub",
        description="Hub congestion",
        status="OPEN",
        dedup_fingerprint=f"lifecycle-test-2-{datetime.now().timestamp()}",
        detected_at=utcnow(),
    )
    db_session.add(alert2)
    db_session.commit()
    db_session.refresh(alert2)

    action2 = AgentActionService.propose_action_for_risk(
        db=db_session,
        alert=alert2,
        risk_dict={"risk_category": alert2.risk_category, "department": alert2.department, "title": alert2.title},
    )
    assert action2 is not None
    assert action2.status == "PROPOSED"

    rejected_action = AgentActionService.reject_action(
        db=db_session,
        action_id=action2.id,
        user=test_user,
        reason="Carrier already communicated delay will be resolved within standard window",
    )
    assert rejected_action.status == "REJECTED"
    assert rejected_action.approved_by == test_user.id
    assert rejected_action.result.get("rejected") is True
    assert "resolved within standard window" in rejected_action.result.get("reason", "")


def test_auto_execute_only_for_allowed_types(db_session, monkeypatch):
    """
    Test setting AGENT3_AUTO_EXECUTE_ACTIONS:
    - Named types run without approval (status immediately EXECUTED)
    - Unnamed types still require approval (status PROPOSED)
    """
    monkeypatch.setenv("AGENT3_AUTO_EXECUTE_ACTIONS", "REQUEST_EXPEDITE,NOTIFY_CUSTOMER_REVISED_DATE")

    order, mon_rec = _get_or_create_monitored_order(db_session)

    # 1. Propose action matching allowed auto-execute type
    alert_expedite = RiskAlert(
        customer_order_id=order.customer_order_id,
        monitoring_record_id=mon_rec.id,
        department="MMS",
        risk_category="RAW_MATERIAL_SHORTAGE",
        severity="HIGH",
        title="Capacitor stock critical",
        description="Safety stock breached",
        status="OPEN",
        dedup_fingerprint=f"auto-exec-expedite-{datetime.now().timestamp()}",
        detected_at=utcnow(),
    )
    db_session.add(alert_expedite)
    db_session.commit()
    db_session.refresh(alert_expedite)

    action_expedite = AgentActionService.propose_action_for_risk(
        db=db_session,
        alert=alert_expedite,
        risk_dict={"risk_category": alert_expedite.risk_category, "department": alert_expedite.department, "title": alert_expedite.title},
    )
    assert action_expedite is not None
    assert action_expedite.action_type == "REQUEST_EXPEDITE"
    assert action_expedite.requires_approval is False
    assert action_expedite.status == "EXECUTED"
    assert action_expedite.executed_at is not None

    # 2. Propose action NOT in allowed auto-execute type (e.g. REQUEST_REASSESSMENT)
    alert_reassessment = RiskAlert(
        customer_order_id=order.customer_order_id,
        monitoring_record_id=mon_rec.id,
        department="ERP",
        risk_category="DELIVERY_DATE_BREACHED",
        severity="CRITICAL",
        title="Delivery SLA exceeded",
        description="Delivery commitment missed by 3 days",
        status="OPEN",
        dedup_fingerprint=f"auto-exec-reassess-{datetime.now().timestamp()}",
        detected_at=utcnow(),
    )
    db_session.add(alert_reassessment)
    db_session.commit()
    db_session.refresh(alert_reassessment)

    action_reassessment = AgentActionService.propose_action_for_risk(
        db=db_session,
        alert=alert_reassessment,
        risk_dict={"risk_category": alert_reassessment.risk_category, "department": alert_reassessment.department, "title": alert_reassessment.title},
    )
    assert action_reassessment is not None
    assert action_reassessment.action_type == "REQUEST_REASSESSMENT"
    assert action_reassessment.requires_approval is True
    assert action_reassessment.status == "PROPOSED"
    assert action_reassessment.executed_at is None


def test_reassessment_creates_revision_and_approval_updates_baseline(db_session, test_manager):
    """
    Requirement 4:
    - REQUEST_REASSESSMENT calls FeasibilityService to reassess order
    - Creates a revised PENDING proposal (revision + 1) linked to the alert
    - Approval of that revised proposal updates the monitoring baseline via activate_monitoring
    """
    order, mon_rec = _get_or_create_monitored_order(db_session)
    order_id = order.customer_order_id

    # Find initial max revision
    initial_max_rev = CommitmentRepository.get_max_revision(db_session, order_id)

    # Create alert for CARRIER_TRANSIT_DELAY -> maps to REQUEST_REASSESSMENT
    alert = RiskAlert(
        customer_order_id=order_id,
        monitoring_record_id=mon_rec.id,
        department="TMS",
        risk_category="CARRIER_TRANSIT_DELAY",
        severity="HIGH",
        title="Major carrier transit delay",
        description="Customs hold in transit corridor",
        status="OPEN",
        dedup_fingerprint=f"reassessment-test-{datetime.now().timestamp()}",
        detected_at=utcnow(),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    action = AgentActionService.propose_action_for_risk(
        db=db_session,
        alert=alert,
        risk_dict={"risk_category": alert.risk_category, "department": alert.department, "title": alert.title},
    )
    assert action is not None
    assert action.action_type == "REQUEST_REASSESSMENT"

    # Approve action to execute the reassessment handoff
    executed_action = AgentActionService.approve_action(
        db=db_session,
        action_id=action.id,
        user=test_manager,
    )
    assert executed_action.status == "EXECUTED"
    assert executed_action.result is not None
    revised_proposal_id = executed_action.result.get("revised_proposal_id")
    assert revised_proposal_id is not None
    assert executed_action.result.get("revision") == initial_max_rev + 1

    # Verify revised proposal in DB
    revised_prop = CommitmentRepository.get_proposal_by_id(db_session, revised_proposal_id)
    assert revised_prop is not None
    assert revised_prop.status == "PENDING"
    assert revised_prop.revision == initial_max_rev + 1
    assert revised_prop.customer_order_id == order_id

    # Now approve this revised proposal as a commercial approver (test_manager)
    approved_prop = WorkflowService.approve_proposal(
        db=db_session,
        proposal_id=revised_prop.id,
        user=test_manager,
        decision_note="Approved revised delivery baseline following carrier delay reassessment",
    )
    assert approved_prop.status == "APPROVED"

    # Verify monitoring record baseline was updated via activate_monitoring
    db_session.refresh(mon_rec)
    assert mon_rec.approved_delivery_date == revised_prop.proposed_date


def test_caps_and_deduplication(db_session, monkeypatch):
    """
    Requirement 6:
    - Skip proposing if an identical open action exists
    - Per-order cap on actions
    - Per-day cap on actions
    """
    order, mon_rec = _get_or_create_monitored_order(db_session)
    order_id = order.customer_order_id

    # 1. Deduplication: Propose an action twice
    alert = RiskAlert(
        customer_order_id=order_id,
        monitoring_record_id=mon_rec.id,
        department="MES",
        risk_category="PRODUCTION_DELAY",
        severity="MEDIUM",
        title="Shift output variation",
        description="Shift variation detected",
        status="OPEN",
        dedup_fingerprint=f"dedup-test-{datetime.now().timestamp()}",
        detected_at=utcnow(),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    first_action = AgentActionService.propose_action_for_risk(
        db=db_session,
        alert=alert,
        risk_dict={"risk_category": alert.risk_category, "department": alert.department, "title": alert.title},
    )
    assert first_action is not None
    assert first_action.status == "PROPOSED"

    # Second call for same order and same action type should return existing open action, NOT create a duplicate
    second_action = AgentActionService.propose_action_for_risk(
        db=db_session,
        alert=alert,
        risk_dict={"risk_category": alert.risk_category, "department": alert.department, "title": alert.title},
    )
    assert second_action is not None
    assert second_action.id == first_action.id

    # 2. Per-order cap test
    # Set cap to current open actions count for this order
    current_count = AgentActionRepository.count_open_actions_for_order(db_session, order_id)
    monkeypatch.setenv("AGENT3_MAX_ACTIONS_PER_ORDER", str(current_count))

    # Try proposing a different action type
    alert_carrier = RiskAlert(
        customer_order_id=order_id,
        monitoring_record_id=mon_rec.id,
        department="TMS",
        risk_category="SHIPMENT_EXCEPTION",
        severity="HIGH",
        title="Freight port strike",
        description="Corridor closed",
        status="OPEN",
        dedup_fingerprint=f"cap-order-test-{datetime.now().timestamp()}",
        detected_at=utcnow(),
    )
    db_session.add(alert_carrier)
    db_session.commit()
    db_session.refresh(alert_carrier)

    capped_order_action = AgentActionService.propose_action_for_risk(
        db=db_session,
        alert=alert_carrier,
        risk_dict={"risk_category": alert_carrier.risk_category, "department": alert_carrier.department, "title": alert_carrier.title},
    )
    assert capped_order_action is None  # Skipped due to per-order cap

    # 3. Per-day cap test
    monkeypatch.delenv("AGENT3_MAX_ACTIONS_PER_ORDER", raising=False)
    today_count = AgentActionRepository.count_daily_actions(db_session)
    monkeypatch.setenv("AGENT3_MAX_ACTIONS_PER_DAY", str(today_count))

    capped_day_action = AgentActionService.propose_action_for_risk(
        db=db_session,
        alert=alert_carrier,
        risk_dict={"risk_category": alert_carrier.risk_category, "department": alert_carrier.department, "title": alert_carrier.title},
    )
    assert capped_day_action is None  # Skipped due to per-day cap


def test_executors_do_not_mutate_source_data(db_session, test_user):
    """
    Requirement 2:
    Action executors must write to audit log and send email; none may edit
    production/inventory source data directly.
    """
    order, mon_rec = _get_or_create_monitored_order(db_session)

    # Record baseline counts of production orders and inventory daily snapshots
    prod_order_count_before = db_session.query(FactProductionOrder).count()
    inv_snapshot_count_before = db_session.query(FactInventoryDailySnapshot).count()

    action = AgentActionRepository.create_action(
        db=db_session,
        customer_order_id=order.customer_order_id,
        action_type="REQUEST_EXPEDITE",
        parameters={"department": "MES", "title": "Priority parts release"},
        requires_approval=True,
        status="PROPOSED",
    )

    executed = AgentActionService.execute_action(db_session, action.id, user=test_user)
    assert executed.status == "EXECUTED"

    # Verify source data table counts did not change
    prod_order_count_after = db_session.query(FactProductionOrder).count()
    inv_snapshot_count_after = db_session.query(FactInventoryDailySnapshot).count()

    assert prod_order_count_after == prod_order_count_before
    assert inv_snapshot_count_after == inv_snapshot_count_before


def test_api_action_endpoints(client, auth_headers, db_session):
    """
    Requirement 5:
    API: GET /api/actions, POST /api/actions/{id}/approve, POST /api/actions/{id}/reject
    """
    order, mon_rec = _get_or_create_monitored_order(db_session)

    action = AgentActionRepository.create_action(
        db=db_session,
        customer_order_id=order.customer_order_id,
        action_type="NOTIFY_CUSTOMER_REVISED_DATE",
        parameters={"title": "Customs inspection delay", "delivery_impact": "2 days variance"},
        requires_approval=True,
        status="PROPOSED",
    )

    # 1. GET /api/actions
    resp = client.get("/api/actions", headers=auth_headers)
    assert resp.status_code == 200
    actions_list = resp.json()
    assert isinstance(actions_list, list)
    matching = [a for a in actions_list if a["id"] == action.id]
    assert len(matching) == 1
    assert matching[0]["action_type"] == "NOTIFY_CUSTOMER_REVISED_DATE"
    assert matching[0]["status"] == "PROPOSED"

    # 2. POST /api/actions/{id}/approve
    resp_approve = client.post(f"/api/actions/{action.id}/approve", headers=auth_headers)
    assert resp_approve.status_code == 200
    approved_data = resp_approve.json()
    assert approved_data["status"] == "EXECUTED"
    assert approved_data["executed_at"] is not None

    # 3. Create another action and test POST /api/actions/{id}/reject
    action2 = AgentActionRepository.create_action(
        db=db_session,
        customer_order_id=order.customer_order_id,
        action_type="REQUEST_CARRIER_UPGRADE",
        parameters={"title": "Transit bottleneck"},
        requires_approval=True,
        status="PROPOSED",
    )

    resp_reject = client.post(
        f"/api/actions/{action2.id}/reject",
        json={"reason": "Premium carrier cost not justified for standard order"},
        headers=auth_headers,
    )
    assert resp_reject.status_code == 200
    rejected_data = resp_reject.json()
    assert rejected_data["status"] == "REJECTED"
    assert rejected_data["result"]["rejected"] is True
