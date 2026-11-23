import pytest
from datetime import datetime, date, timedelta, timezone
from fastapi.testclient import TestClient

from app.models.auth import User
from app.models.workflow import (
    RiskAlert,
    EmailNotificationLog,
    DepartmentContact,
    DepartmentMapping,
    CommitmentProposal,
    OrderMonitoringRecord,
    AuditLog,
)
from app.models.business import FactCustomerOrder, DimCustomer, DimProduct
from app.services.email_service import EmailService, MockEmailProvider
from app.services.auth_service import create_access_token, hash_password
from app.services.monitoring_service import MonitoringService
from app.security.permissions import Permission, get_user_permissions


def utcnow():
    return datetime.now(timezone.utc)


@pytest.fixture
def mock_email():
    """Inject mock email provider and restore original after test."""
    mock = MockEmailProvider()
    EmailService.set_provider(mock)
    yield mock
    EmailService.reset_provider()


@pytest.fixture
def rbac_users(db_session):
    """Seed distinct users representing each RBAC role."""
    # 1. Admin
    admin = db_session.query(User).filter(User.email == "test_admin@mfg.com").first()
    if not admin:
        admin = User(
            email="test_admin@mfg.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Admin Test",
            role="admin",
            can_approve_commitments=True,
            is_active=True,
        )
        db_session.add(admin)

    # 2. Customer Service Approver (with approval permission)
    cs_approver = db_session.query(User).filter(User.email == "test_cs_approver@mfg.com").first()
    if not cs_approver:
        cs_approver = User(
            email="test_cs_approver@mfg.com",
            hashed_password=hash_password("Pass123!"),
            full_name="CS Approver Test",
            role="customer_service",
            department="CUSTOMER_SERVICE",
            can_approve_commitments=True,
            is_active=True,
        )
        db_session.add(cs_approver)

    # 3. Customer Service Rep (WITHOUT approval permission)
    cs_rep = db_session.query(User).filter(User.email == "test_cs_rep@mfg.com").first()
    if not cs_rep:
        cs_rep = User(
            email="test_cs_rep@mfg.com",
            hashed_password=hash_password("Pass123!"),
            full_name="CS Rep Test",
            role="customer_service",
            department="CUSTOMER_SERVICE",
            can_approve_commitments=False,
            is_active=True,
        )
        db_session.add(cs_rep)

    # 4. Operational user (MMS department)
    op_mms = db_session.query(User).filter(User.email == "test_op_mms@mfg.com").first()
    if not op_mms:
        op_mms = User(
            email="test_op_mms@mfg.com",
            hashed_password=hash_password("Pass123!"),
            full_name="MMS Specialist Test",
            role="operational",
            department="MMS",
            can_approve_commitments=False,
            is_active=True,
        )
        db_session.add(op_mms)

    # 5. Operational user (QMS department)
    op_qms = db_session.query(User).filter(User.email == "test_op_qms@mfg.com").first()
    if not op_qms:
        op_qms = User(
            email="test_op_qms@mfg.com",
            hashed_password=hash_password("Pass123!"),
            full_name="QMS Specialist Test",
            role="operational",
            department="QMS",
            can_approve_commitments=False,
            is_active=True,
        )
        db_session.add(op_qms)

    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(cs_approver)
    db_session.refresh(cs_rep)
    db_session.refresh(op_mms)
    db_session.refresh(op_qms)

    return {
        "admin": admin,
        "cs_approver": cs_approver,
        "cs_rep": cs_rep,
        "op_mms": op_mms,
        "op_qms": op_qms,
    }


def make_headers(user: User):
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. AUTHENTICATION & RBAC TESTS
# ==============================================================================

def test_unauthenticated_requests_return_401(client: TestClient):
    """Protected endpoints reject requests without JWT with 401 Unauthorized."""
    res1 = client.get("/api/auth/me")
    assert res1.status_code == 401

    res2 = client.get("/api/auth/users")
    assert res2.status_code == 401

    res3 = client.get("/api/commitment-proposals")
    assert res3.status_code == 401


def test_rbac_permission_computation(rbac_users):
    """Verifies calculated permissions set per role and authority flag."""
    admin = rbac_users["admin"]
    cs_approver = rbac_users["cs_approver"]
    cs_rep = rbac_users["cs_rep"]
    op_mms = rbac_users["op_mms"]

    admin_perms = get_user_permissions(admin)
    assert Permission.USER_MANAGE in admin_perms
    assert Permission.COMMITMENT_APPROVE in admin_perms

    cs_app_perms = get_user_permissions(cs_approver)
    assert Permission.COMMITMENT_APPROVE in cs_app_perms
    assert Permission.COMMUNICATION_RECORD in cs_app_perms
    assert Permission.USER_MANAGE not in cs_app_perms

    cs_rep_perms = get_user_permissions(cs_rep)
    assert Permission.COMMITMENT_APPROVE not in cs_rep_perms
    assert Permission.COMMUNICATION_RECORD in cs_rep_perms

    mms_perms = get_user_permissions(op_mms)
    assert Permission.ALERT_ACKNOWLEDGE in mms_perms
    assert Permission.ALERT_RESOLVE in mms_perms
    assert Permission.COMMITMENT_APPROVE not in mms_perms


def test_commercial_approver_authorization(client: TestClient, db_session, rbac_users):
    """
    Authorized approver can approve commercial commitment.
    Unauthorized CS Rep without explicit permission receives 403 Forbidden.
    """
    admin = rbac_users["admin"]
    cs_approver = rbac_users["cs_approver"]
    cs_rep = rbac_users["cs_rep"]

    # Create dummy proposal
    proposal = CommitmentProposal(
        customer_order_id="PRE-TEST-9901",
        proposed_date=date.today() + timedelta(days=10),
        recommended_by="agent",
        status="PENDING",
        created_by=admin.id,
        revision=1,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)

    # 1. CS Rep without approval authority receives 403 Forbidden
    rep_res = client.post(
        f"/api/commitment-proposals/{proposal.id}/approve",
        headers=make_headers(cs_rep),
        json={"decision_note": "Attempted by unauthorized rep"},
    )
    assert rep_res.status_code == 403
    err_body = rep_res.json()
    err_msg = err_body.get("error") or err_body.get("detail", "")
    assert "Commercial commitment approval authority required" in err_msg

    # 2. Authorized CS Approver succeeds with 200 OK
    app_res = client.post(
        f"/api/commitment-proposals/{proposal.id}/approve",
        headers=make_headers(cs_approver),
        json={"decision_note": "Approved by authorized Customer Service Approver"},
    )
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"


def test_department_boundary_access_control(client: TestClient, db_session, rbac_users):
    """
    Operational user in MMS cannot acknowledge or resolve an alert for QMS.
    Attempting cross-department mutation returns 403 Forbidden.
    """
    op_mms = rbac_users["op_mms"]
    op_qms = rbac_users["op_qms"]

    # Create QMS alert
    qms_alert = RiskAlert(
        customer_order_id="CO-TEST-8801",
        department="QMS",
        risk_category="QUALITY_HOLD",
        severity="HIGH",
        title="Quality Hold on SMT Line",
        description="SMT Line 2 visual inspection failure",
        status="OPEN",
        dedup_fingerprint="fp-qms-8801",
    )
    db_session.add(qms_alert)
    db_session.commit()
    db_session.refresh(qms_alert)

    # MMS specialist receives 403 Forbidden when accessing QMS alert
    res_ack = client.post(
        f"/api/alerts/{qms_alert.id}/acknowledge",
        headers=make_headers(op_mms),
    )
    assert res_ack.status_code == 403
    ack_body = res_ack.json()
    ack_msg = ack_body.get("error") or ack_body.get("detail", "")
    assert "cannot access restricted department 'QMS'" in ack_msg

    # QMS specialist can acknowledge their own department alert
    res_ack_ok = client.post(
        f"/api/alerts/{qms_alert.id}/acknowledge",
        headers=make_headers(op_qms),
    )
    assert res_ack_ok.status_code == 200
    assert res_ack_ok.json()["status"] == "ACKNOWLEDGED"


def test_customer_service_cannot_resolve_operational_alerts(client: TestClient, db_session, rbac_users):
    """
    Customer Service users cannot modify operational department findings.
    Returns 403 Forbidden.
    """
    cs_rep = rbac_users["cs_rep"]
    mes_alert = RiskAlert(
        customer_order_id="CO-TEST-8802",
        department="MES",
        risk_category="PRODUCTION_DELAY",
        severity="HIGH",
        title="Assembly station downtime",
        description="Conveyor motor failure",
        status="OPEN",
        dedup_fingerprint="fp-mes-8802",
    )
    db_session.add(mes_alert)
    db_session.commit()
    db_session.refresh(mes_alert)

    res = client.post(
        f"/api/alerts/{mes_alert.id}/resolve",
        headers=make_headers(cs_rep),
        json={"resolution_notes": "Attempted resolve by CS"},
    )
    assert res.status_code == 403


def test_admin_user_management_and_audit(client: TestClient, db_session, rbac_users):
    """
    Only Administrator can manage users.
    Creating a user records an audit log entry.
    """
    admin = rbac_users["admin"]
    cs_rep = rbac_users["cs_rep"]

    # Non-admin receives 403
    res_forbidden = client.get("/api/auth/users", headers=make_headers(cs_rep))
    assert res_forbidden.status_code == 403

    # Admin lists users
    res_ok = client.get("/api/auth/users", headers=make_headers(admin))
    assert res_ok.status_code == 200
    assert isinstance(res_ok.json(), list)

    # Admin creates new operational user
    new_email = "new_mes_user@mfg.com"
    res_create = client.post(
        "/api/auth/users",
        headers=make_headers(admin),
        json={
            "email": new_email,
            "full_name": "New MES Operator",
            "password": "Password123!",
            "role": "operational",
            "department": "MES",
            "can_approve_commitments": False,
        },
    )
    assert res_create.status_code == 201
    assert res_create.json()["email"] == new_email

    # Check audit log
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "CREATE_USER",
        AuditLog.user_id == admin.id,
    ).first()
    assert audit_entry is not None
    assert audit_entry.payload["created_email"] == new_email


# ==============================================================================
# 2. OPERATIONAL NOTIFICATIONS & DEPARTMENT ROUTING TESTS
# ==============================================================================

def test_operational_notifications_department_routing(db_session, mock_email):
    """
    Verifies that issues reach the designated responsible departments:
    - Raw material shortage reaches MMS
    - Production delay reaches MES
    - Quality hold reaches QMS
    - Warehouse delay reaches WMS
    - Shipment issue reaches TMS
    - Order/commercial validation reaches ERP
    - Engineering revision reaches PLM
    """
    dept_test_cases = [
        ("MMS", "RAW_MATERIAL_SHORTAGE", "CRITICAL", "Shortage of PMIC ICs"),
        ("MES", "PRODUCTION_DELAY", "HIGH", "Line 3 SMD feeder calibration"),
        ("QMS", "QUALITY_HOLD", "HIGH", "Visual inspection failure lot #441"),
        ("WMS", "WAREHOUSE_PICKING_PACKAGING", "MEDIUM", "Packaging carton staging delay"),
        ("TMS", "CARRIER_TRANSIT_DELAY", "HIGH", "Freight carrier customs hold"),
        ("ERP", "PO_COMMERCIAL_VALIDATION", "CRITICAL", "Sales order header mismatch"),
        ("PLM", "PRODUCT_CONFIG_ENGINEERING_REVISION", "MEDIUM", "Engineering revision REV-C hold"),
    ]

    for dept, cat, sev, title in dept_test_cases:
        alert = RiskAlert(
            customer_order_id=f"ORD-{dept}-01",
            department=dept,
            risk_category=cat,
            severity=sev,
            title=title,
            description=f"Automated test for {dept} {cat}",
            delivery_impact="Potential 2-day delivery extension",
            recommended_action=f"Investigate in {dept} queue",
            status="OPEN",
            dedup_fingerprint=f"fp-{dept}-{cat}",
            detected_at=utcnow(),
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)

        log = EmailService.send_operational_risk_notification(
            db=db_session,
            alert=alert,
            customer_name="Global Devices Inc.",
            required_date="2026-11-25",
            approved_date="2026-11-25",
        )

        assert log is not None
        assert log.status == "SENT"
        assert log.department == dept
        assert log.recipient_category == "OPERATIONAL"
        assert f"Action Required – {title} – Order ORD-{dept}-01" in log.subject
        assert dept in log.recipient_email or "manufacturing.internal" in log.recipient_email


# ==============================================================================
# 3. CUSTOMER SERVICE INDEPENDENT NOTIFICATION TESTS
# ==============================================================================

def test_customer_service_receives_independent_notification(db_session, mock_email):
    """
    Customer Service independently receives customer-impacting delivery risk alerts.
    Contains customer name, delivery impact, and explicit guidance that revised date is not confirmed.
    """
    alert = RiskAlert(
        customer_order_id="ORD-1024",
        department="MMS",
        risk_category="RAW_MATERIAL_SHORTAGE",
        severity="HIGH",
        title="Raw Material Shortage – PMIC Component",
        description="Raw material inventory for PMIC components below safety threshold.",
        delivery_impact="Potential 3-day assembly schedule delay.",
        recommended_action="Coordinate with supplier.",
        status="OPEN",
        dedup_fingerprint="fp-ord-1024",
        detected_at=utcnow(),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # 1. Operational notification
    op_log = EmailService.send_operational_risk_notification(
        db=db_session,
        alert=alert,
        customer_name="Retailer North",
        required_date="2026-11-20",
    )
    assert op_log is not None
    assert op_log.recipient_category == "OPERATIONAL"

    # 2. Independent Customer Service notification
    cs_log = EmailService.send_customer_service_notification(
        db=db_session,
        alert=alert,
        customer_name="Retailer North",
        required_date="2026-11-20",
    )
    assert cs_log is not None
    assert cs_log.recipient_category == "CUSTOMER_SERVICE"
    assert "Delivery Risk Alert – Order ORD-1024" in cs_log.subject
    assert "Retailer North" in cs_log.body_text
    assert "The revised delivery date has not yet been confirmed." in cs_log.body_text
    assert "Do NOT send unverified delivery promises to customers." in cs_log.body_text


# ==============================================================================
# 4. EMAIL RELIABILITY, DUPLICATION PREVENTION & ESCALATION TESTS
# ==============================================================================

def test_duplicate_email_suppression_and_severity_escalation(db_session, mock_email):
    """
    1. Unchanged issue does NOT trigger duplicate emails (Rule 1).
    2. Severity escalation (MEDIUM -> CRITICAL) triggers escalated email (Rule 2).
    """
    alert = RiskAlert(
        customer_order_id="ORD-DEDUP-01",
        department="MES",
        risk_category="PRODUCTION_DELAY",
        severity="MEDIUM",
        title="Line 1 minor slow run",
        description="Line running at 85% capacity",
        status="OPEN",
        dedup_fingerprint="fp-dedup-01",
        detected_at=utcnow(),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # First send: Dispatched
    first_send = EmailService.send_operational_risk_notification(db=db_session, alert=alert)
    assert first_send is not None
    assert first_send.status == "SENT"
    initial_sent_count = len(mock_email.sent_emails)

    # Second send without severity change: Suppressed!
    second_send = EmailService.send_operational_risk_notification(db=db_session, alert=alert)
    assert second_send is None
    assert len(mock_email.sent_emails) == initial_sent_count

    # Escalate severity to CRITICAL
    alert.severity = "CRITICAL"
    alert.title = "Line 1 completely stopped"
    db_session.commit()

    escalated_send = EmailService.send_operational_risk_notification(db=db_session, alert=alert)
    assert escalated_send is not None
    assert escalated_send.notification_type == "RISK_ESCALATION"
    assert len(mock_email.sent_emails) == initial_sent_count + 1


def test_issue_resolution_notifies_both_operational_and_cs(db_session, mock_email):
    """
    When an issue is resolved, resolution notifications are dispatched
    to both the operational department and Customer Service (Rule 4).
    """
    alert = RiskAlert(
        customer_order_id="ORD-RES-01",
        department="TMS",
        risk_category="CARRIER_TRANSIT_DELAY",
        severity="HIGH",
        title="Transit carrier vehicle replacement",
        description="Carrier vehicle experienced tire puncture",
        status="OPEN",
        dedup_fingerprint="fp-res-01",
        detected_at=utcnow(),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # Resolve alert
    alert.status = "RESOLVED"
    alert.resolved_at = utcnow()
    alert.resolution_notes = "Carrier dispatched replacement tractor; ETA restored to on-schedule."
    db_session.commit()

    res_logs = EmailService.send_resolution_notification(
        db=db_session,
        alert=alert,
        customer_name="MobileMart",
        resolved_by_name="Logistics Dispatcher",
    )

    assert len(res_logs) == 2
    cats = [l.recipient_category for l in res_logs]
    assert "OPERATIONAL" in cats
    assert "CUSTOMER_SERVICE" in cats
    for l in res_logs:
        assert l.status == "SENT"
        assert "Resolved – Manufacturing Alert" in l.subject


def test_missing_provider_configuration_and_bounded_retry(db_session):
    """
    1. Missing SMTP config preserves notification as PENDING_CONFIG (Rule 10).
    2. Simulated provider failure records FAILED status.
    3. Retrying increments attempt count and resolves upon successful response (Rule 8).
    """
    # 1. Unconfigured provider
    unconfigured_provider = MockEmailProvider(simulate_failure=True, failure_reason="Simulated unconfigured")
    unconfigured_provider.is_configured = lambda: False
    EmailService.set_provider(unconfigured_provider)

    alert = RiskAlert(
        customer_order_id="ORD-RETRY-01",
        department="WMS",
        risk_category="WAREHOUSE_PICKING_PACKAGING",
        severity="MEDIUM",
        title="Packaging box shortage",
        description="Master cartons awaiting replenishment",
        status="OPEN",
        dedup_fingerprint="fp-retry-01",
        detected_at=utcnow(),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    pending_log = EmailService.send_operational_risk_notification(db=db_session, alert=alert)
    assert pending_log is not None
    assert pending_log.status == "PENDING_CONFIG"

    # 2. Simulate working provider on retry
    working_mock = MockEmailProvider()
    EmailService.set_provider(working_mock)

    retried_log = EmailService.retry_failed_notification(db=db_session, log_id=pending_log.id)
    assert retried_log.status == "SENT"
    assert retried_log.retry_count == 1
    assert retried_log.provider_message_id is not None
