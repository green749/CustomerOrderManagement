import html
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.auth import User
from ..models.workflow import RiskAlert, EmailNotificationLog, DepartmentContact
from ..schemas.workflow import (
    RiskAlertResponse,
    AlertAssignRequest,
    AlertResolveRequest,
    EmailNotificationResponse,
    DepartmentContactResponse,
)
from ..schemas.auth import CustomerCommunicationRequest
from ..services.auth_service import get_current_user
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from ..models.business import FactCustomerOrder
from ..security.permissions import (
    require_permission,
    verify_department_access,
    require_admin,
    Permission,
)
from ..services.monitoring_service import MonitoringService
from ..services.email_service import EmailService

alerts_router = APIRouter(prefix="/api/alerts", tags=["Agent 3 - Risk Alerts & Notifications"])


@alerts_router.get("", response_model=List[RiskAlertResponse])
def list_alerts(
    severity: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    customer_order_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List monitoring agent alerts.
    Enforces department boundary for operational users: operational users are scoped
    to their assigned department and cannot access other restricted departments.
    """
    user_role = (current_user.role or "").lower().strip()
    effective_dept = department

    # Operational department user boundary enforcement
    if user_role == "operational" and current_user.department:
        if department and department.upper().strip() != current_user.department.upper().strip():
            verify_department_access(current_user, department)
        effective_dept = current_user.department.upper().strip()

    items, total = MonitoringService.list_alerts(
        db=db,
        severity=severity,
        department=effective_dept,
        status=status_filter,
        customer_order_id=customer_order_id,
        page=page,
        page_size=page_size,
    )
    return items


@alerts_router.get("/summary")
def get_alerts_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated alert metrics for the Dashboard / Alerts view."""
    q = db.query(RiskAlert)
    user_role = (current_user.role or "").lower().strip()
    if user_role == "operational" and current_user.department:
        q = q.filter(RiskAlert.department == current_user.department.upper().strip())

    total_open = q.filter(RiskAlert.status == "OPEN").count()
    critical_count = q.filter(RiskAlert.status == "OPEN", RiskAlert.severity == "CRITICAL").count()
    high_count = q.filter(RiskAlert.status == "OPEN", RiskAlert.severity == "HIGH").count()
    acknowledged_count = q.filter(RiskAlert.status == "ACKNOWLEDGED").count()
    resolved_count = q.filter(RiskAlert.status == "RESOLVED").count()

    return {
        "total_open": total_open,
        "critical": critical_count,
        "high": high_count,
        "acknowledged": acknowledged_count,
        "resolved": resolved_count,
    }


@alerts_router.post("/{alert_id}/acknowledge", response_model=RiskAlertResponse)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALERT_ACKNOWLEDGE)),
):
    """
    Acknowledge an open risk alert.
    Restricted to authorized operational or admin personnel belonging to the responsible department.
    Customer Service cannot modify operational department findings.
    """
    alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert #{alert_id} not found.")

    # Department boundary check
    verify_department_access(current_user, alert.department)

    return MonitoringService.acknowledge_alert(db, alert_id, current_user)


@alerts_router.post("/{alert_id}/assign", response_model=RiskAlertResponse)
def assign_alert(
    alert_id: int,
    payload: AlertAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALERT_ACKNOWLEDGE)),
):
    """Assign an owner to a risk alert within the responsible department."""
    alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert #{alert_id} not found.")

    verify_department_access(current_user, alert.department)

    return MonitoringService.assign_alert(db, alert_id, payload.assigned_owner, current_user)


@alerts_router.post("/{alert_id}/resolve", response_model=RiskAlertResponse)
def resolve_alert(
    alert_id: int,
    payload: AlertResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALERT_RESOLVE)),
):
    """
    Resolve a risk alert and record verified corrective actions.
    Restricted to authorized operational department personnel or Administrator.
    Dispatches resolution notifications to operational department and Customer Service.
    """
    alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert #{alert_id} not found.")

    verify_department_access(current_user, alert.department)

    return MonitoringService.resolve_alert(db, alert_id, payload.resolution_notes, current_user)


@alerts_router.post("/{alert_id}/customer-communication", response_model=RiskAlertResponse)
def record_customer_communication(
    alert_id: int,
    payload: CustomerCommunicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMUNICATION_RECORD)),
):
    """
    Record that a delivery risk or schedule issue was communicated to the customer.
    Available to Customer Service and Administrator roles.
    """
    alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert #{alert_id} not found.")

    return MonitoringService.record_customer_communication(
        db=db,
        alert_id=alert_id,
        notes=payload.customer_communication_notes,
        user=current_user,
    )


@alerts_router.get("/notifications", response_model=List[EmailNotificationResponse])
def list_email_notifications(
    customer_order_id: Optional[str] = Query(None),
    recipient_category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List email notification dispatch logs with recipient category and delivery status."""
    q = db.query(EmailNotificationLog)
    if customer_order_id:
        q = q.filter(EmailNotificationLog.customer_order_id == customer_order_id)
    if recipient_category:
        q = q.filter(EmailNotificationLog.recipient_category == recipient_category.upper().strip())

    # Operational department users only see their department's notifications
    user_role = (current_user.role or "").lower().strip()
    if user_role == "operational" and current_user.department:
        q = q.filter(EmailNotificationLog.department == current_user.department.upper().strip())

    return q.order_by(EmailNotificationLog.created_at.desc()).limit(limit).all()


@alerts_router.get("/contacts", response_model=List[DepartmentContactResponse])
def list_department_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List configured department and customer service email recipients."""
    return db.query(DepartmentContact).all()


@alerts_router.post("/notifications/{log_id}/retry", response_model=EmailNotificationResponse)
def retry_notification(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTIFICATION_RETRY)),
):
    """Retry an individual failed or pending-config email notification."""
    try:
        return EmailService.retry_failed_notification(db, log_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@alerts_router.post("/notifications/retry-failed")
def retry_all_failed_notifications(
    max_retries: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTIFICATION_RETRY)),
):
    """Batch retry all failed email notifications under max retry limit."""
    return EmailService.retry_all_failed_notifications(db, max_retries=max_retries)


@alerts_router.post("/{alert_id}/dispatch-notification")
def dispatch_alert_notification(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MONITORING_TRIGGER)),
):
    """
    Manually dispatch email notifications for an active risk alert to the configured
    Operational Department and Customer Service recipients immediately.
    """
    alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert #{alert_id} not found.")

    order = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == alert.customer_order_id).first()
    cust_name = order.customer.customer_name if (order and order.customer) else None
    prod_name = order.product.product_name if (order and order.product) else None
    prod_qty = order.order_qty if order else None
    req_date = str(order.requested_delivery_date) if (order and order.requested_delivery_date) else None
    app_date = str(order.confirmed_delivery_date or order.requested_delivery_date or "Pending Confirmation")

    op_log = EmailService.send_operational_risk_notification(
        db=db,
        alert=alert,
        customer_name=cust_name,
        product_name=prod_name,
        product_qty=prod_qty,
        required_date=req_date,
        approved_date=app_date,
        force_send=True,
    )

    cs_log = EmailService.send_customer_service_notification(
        db=db,
        alert=alert,
        customer_name=cust_name,
        required_date=req_date,
        approved_date=app_date,
        estimated_achievable_date=app_date,
        force_send=True,
    )

    return {
        "alert_id": alert.id,
        "order_id": alert.customer_order_id,
        "operational_notification": {
            "id": op_log.id if op_log else None,
            "recipient": op_log.recipient_email if op_log else None,
            "status": op_log.status if op_log else None,
            "subject": op_log.subject if op_log else None,
        },
        "customer_service_notification": {
            "id": cs_log.id if cs_log else None,
            "recipient": cs_log.recipient_email if cs_log else None,
            "status": cs_log.status if cs_log else None,
            "subject": cs_log.subject if cs_log else None,
        },
    }


class TestEmailRequest(BaseModel):
    recipient_email: str
    recipient_category: Optional[str] = "CUSTOMER_SERVICE"


@alerts_router.post("/test-notification")
def send_test_notification(
    payload: TestEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Send a test surveillance notification to verify provider connectivity and email delivery.
    """
    recipient = payload.recipient_email.strip().lower()
    subject = f"[TEST] Manufacturing 360 – Surveillance Test Notification"
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    body = EmailService.render_neat_plain_text(
        title="Surveillance Connectivity Test",
        order_id="TEST-000001",
        customer_name="Manufacturing 360 Enterprise Client",
        product_info="Production Telemetry Probe v2.4 (Qty: 100)",
        department="CUSTOMER_SERVICE",
        severity="LOW",
        issue_category="CONNECTIVITY_CHECK",
        impact_status="System Verified (Nominal)",
        description=f"This is an automated connectivity test dispatched by Agent 3 (Order Surveillance).\nTriggered by: {current_user.full_name} ({current_user.email})\nDispatched At: {now_str}",
        delivery_impact="Zero operational disruption. Email delivery conduits and routing are operational.",
        action_required="No action required. Notification infrastructure is functioning properly.",
        order_link="http://localhost:5173/monitoring",
        queue_link="http://localhost:5173/settings",
        governance_notice="Automated connectivity verification for Ethereal / SMTP mail conduit.",
    )
    html_body = EmailService.render_neat_email_html(
        title="Surveillance Connectivity Test",
        order_id="TEST-000001",
        customer_name="Manufacturing 360 Enterprise Client",
        product_info="Production Telemetry Probe v2.4 (Qty: 100)",
        department="CUSTOMER_SERVICE",
        severity="LOW",
        issue_category="CONNECTIVITY_CHECK",
        impact_status="System Verified (Nominal)",
        description=f"This is an automated connectivity test dispatched by Agent 3 (Order Surveillance).<br>Triggered by: <strong>{html.escape(current_user.full_name or 'Admin')}</strong> ({html.escape(current_user.email or '')})<br>Dispatched At: {now_str}",
        delivery_impact="Zero operational disruption. Email delivery conduits and routing are operational.",
        action_required="No action required. Notification infrastructure is functioning properly.",
        order_link="http://localhost:5173/monitoring",
        queue_link="http://localhost:5173/settings",
        recipient_category=payload.recipient_category or "CUSTOMER_SERVICE",
        governance_notice="Automated connectivity verification for Ethereal / SMTP mail conduit.",
    )
    log = EmailService._dispatch_and_persist_notification(
        db=db,
        alert_id=None,
        customer_order_id="TEST-000001",
        recipient_email=recipient,
        recipient_category=payload.recipient_category or "CUSTOMER_SERVICE",
        department="CUSTOMER_SERVICE",
        notification_type="TEST_DISPATCH",
        subject=subject,
        body_text=body,
        html_body=html_body,
    )
    return {
        "id": log.id,
        "recipient_email": log.recipient_email,
        "status": log.status,
        "failure_reason": log.failure_reason,
        "sent_at": log.sent_at.isoformat() if log.sent_at else None,
    }


@alerts_router.post("/check-followups")
def check_unresolved_followups(
    force_send_all: bool = Query(False, description="Force send follow-up even if recently sent"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Agent 3 Surveillance Action:
    Scans all active risk alerts. If an alert has remained unresolved for 3+ days
    after its initial risk notification email was sent, dispatches an automated
    follow-up escalation email to the responsible department and Customer Service.
    """
    try:
        return MonitoringService.check_and_send_unresolved_followup_emails(
            db=db,
            force_send_all=force_send_all,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@alerts_router.post("/{alert_id}/send-followup")
def send_alert_followup(
    alert_id: int,
    force_send: bool = Query(True, description="Force send immediate follow-up"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually dispatch an Agent 3 follow-up escalation email for a specific unresolved alert.
    """
    try:
        return MonitoringService.send_followup_for_alert(
            db=db,
            alert_id=alert_id,
            user=current_user,
            force_send=force_send,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


