import os
from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, selectinload

from ..database import get_db
from ..config import settings
from ..agent.domo_client import is_domo_configured
from ..models.auth import User
from ..models.workflow import OrderMonitoringRecord, MonitoringExecutionLog, EmailNotificationLog, AgentRun
from ..schemas.workflow import OrderMonitoringResponse
from ..security.permissions import require_permission, Permission
from ..services.auth_service import get_current_user
from ..services.monitoring_service import MonitoringService

monitoring_router = APIRouter(prefix="/api/monitoring", tags=["Agent 3 - Order Monitoring & Risk Management"])


class ActivateMonitoringRequest(BaseModel):
    customer_order_id: str = Field(..., description="Customer order ID e.g. CO-001419")
    approved_delivery_date: date = Field(..., description="Customer service approved delivery date")


@monitoring_router.post("/activate", response_model=OrderMonitoringResponse, status_code=status.HTTP_201_CREATED)
def activate_monitoring(
    payload: ActivateMonitoringRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMITMENT_APPROVE)),
):
    """
    AGENT 3 TRIGGER: Activate monitoring for a confirmed customer order.
    Requires commercial approval permission or administrator authority.
    """
    try:
        from ..models.business import FactCustomerOrder
        from ..models.workflow import CommitmentProposal

        ord_obj = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == payload.customer_order_id).first()
        pending_prop = db.query(CommitmentProposal).filter(
            CommitmentProposal.customer_order_id == payload.customer_order_id,
            CommitmentProposal.status == "PENDING"
        ).first()

        if (ord_obj and ord_obj.order_status in ["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING"]) or pending_prop:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order '{payload.customer_order_id}' has pending human approval. Approve the commercial proposal in My Work or Assessments before activating Agent 3 monitoring."
            )

        rec = MonitoringService.activate_monitoring(
            db=db,
            customer_order_id=payload.customer_order_id,
            approved_delivery_date=payload.approved_delivery_date,
            user_id=current_user.id,
        )
        return rec
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@monitoring_router.get("/records", response_model=List[OrderMonitoringResponse])
def list_monitoring_records(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None, description="Search by order ID"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MONITORING_VIEW)),
):
    """List orders currently monitored by Agent 3 with enriched order info. Excludes orders pending human approval."""
    from ..models.business import FactCustomerOrder
    from ..models.workflow import CommitmentProposal

    q = (
        db.query(OrderMonitoringRecord)
        .options(selectinload(OrderMonitoringRecord.alerts))
        .join(FactCustomerOrder, FactCustomerOrder.customer_order_id == OrderMonitoringRecord.customer_order_id)
        .filter(
            FactCustomerOrder.order_status.notin_(["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING", "CANCELLED", "REJECTED"])
        )
    )
    if isinstance(status_filter, str) and status_filter.strip() and status_filter.upper() != "ALL":
        q = q.filter(OrderMonitoringRecord.status == status_filter.upper())
    if isinstance(search, str) and search.strip():
        s_clean = search.strip().replace("Order #", "").replace("Order ", "").strip()
        q = q.filter(
            (OrderMonitoringRecord.customer_order_id.ilike(f"%{s_clean}%"))
            | (OrderMonitoringRecord.customer_order_id.ilike(f"%{s_clean.replace(' ', '-')}%"))
        )
    effective_limit = limit if isinstance(limit, int) else 100
    records = q.order_by(OrderMonitoringRecord.started_at.desc()).limit(effective_limit).all()

    order_ids = [r.customer_order_id for r in records]
    orders_map = {}
    if order_ids:
        orders = (
            db.query(FactCustomerOrder)
            .filter(FactCustomerOrder.customer_order_id.in_(order_ids))
            .options(joinedload(FactCustomerOrder.customer), joinedload(FactCustomerOrder.product))
            .all()
        )
        orders_map = {o.customer_order_id: o for o in orders}

    results = []
    for r in records:
        ord_obj = orders_map.get(r.customer_order_id)
        open_cnt = sum(1 for a in (r.alerts or []) if a.status == "OPEN")
        results.append(
            OrderMonitoringResponse(
                id=r.id,
                customer_order_id=r.customer_order_id,
                approved_delivery_date=r.approved_delivery_date,
                status=r.status,
                baseline_milestones=r.baseline_milestones,
                started_at=r.started_at,
                last_checked_at=r.last_checked_at,
                closed_at=r.closed_at,
                closure_reason=r.closure_reason,
                created_at=r.created_at,
                customer_name=ord_obj.customer.customer_name if (ord_obj and ord_obj.customer) else None,
                product_name=ord_obj.product.product_name if (ord_obj and ord_obj.product) else None,
                order_qty=ord_obj.order_qty if ord_obj else None,
                open_alerts_count=open_cnt,
            )
        )
    return results


@monitoring_router.get("/records/{customer_order_id}", response_model=OrderMonitoringResponse)
def get_monitoring_record(
    customer_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MONITORING_VIEW)),
):
    """Retrieve monitoring state for a specific order."""
    clean_id = customer_order_id.replace("PRE-", "").replace("Order #", "").replace("Order ", "").strip()
    rec = (
        db.query(OrderMonitoringRecord)
        .options(selectinload(OrderMonitoringRecord.alerts))
        .filter(
            (OrderMonitoringRecord.customer_order_id == customer_order_id)
            | (OrderMonitoringRecord.customer_order_id == f"PRE-{clean_id}")
            | (OrderMonitoringRecord.customer_order_id == clean_id)
        )
        .first()
    )
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No monitoring record for order '{customer_order_id}'.")
    from ..models.business import FactCustomerOrder
    from ..models.workflow import CommitmentProposal

    ord_obj = (
        db.query(FactCustomerOrder)
        .filter(FactCustomerOrder.customer_order_id == rec.customer_order_id)
        .options(joinedload(FactCustomerOrder.customer), joinedload(FactCustomerOrder.product))
        .first()
    )
    pending_prop = db.query(CommitmentProposal).filter(
        CommitmentProposal.customer_order_id == rec.customer_order_id,
        CommitmentProposal.status == "PENDING"
    ).first()

    if (ord_obj and ord_obj.order_status in ["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING"]) or pending_prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{customer_order_id}' is currently pending human approval (Stage 3) and has not entered active surveillance (Stage 4)."
        )

    open_cnt = sum(1 for a in (rec.alerts or []) if a.status == "OPEN")
    return OrderMonitoringResponse(
        id=rec.id,
        customer_order_id=rec.customer_order_id,
        approved_delivery_date=rec.approved_delivery_date,
        status=rec.status,
        baseline_milestones=rec.baseline_milestones,
        started_at=rec.started_at,
        last_checked_at=rec.last_checked_at,
        closed_at=rec.closed_at,
        closure_reason=rec.closure_reason,
        created_at=rec.created_at,
        customer_name=ord_obj.customer.customer_name if (ord_obj and ord_obj.customer) else None,
        product_name=ord_obj.product.product_name if (ord_obj and ord_obj.product) else None,
        order_qty=ord_obj.order_qty if ord_obj else None,
        open_alerts_count=open_cnt,
    )


@monitoring_router.post("/run-cycle")
def trigger_monitoring_cycle(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MONITORING_TRIGGER)),
):
    """
    Manually trigger a daily monitoring cycle across all active orders.
    Restricted to users with monitoring trigger permission (Administrators and Managers).
    """
    log = MonitoringService.run_daily_monitoring_cycle(db, cycle_type="MANUAL")
    emails_sent = getattr(log, "emails_dispatched", 0)

    agent_mode = os.environ.get("MONITORING_AGENT_MODE", getattr(settings, "monitoring_agent_mode", "rules")).strip().lower()
    is_agentic_configured = (agent_mode == "agentic" and is_domo_configured())

    latest_run = (
        db.query(AgentRun)
        .filter(AgentRun.agent_name == "agent3")
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    latest_agent_run_id = latest_run.id if latest_run else None
    result_source = "AGENT" if is_agentic_configured else "RULES"
    agent_status = latest_run.status if (latest_run and is_agentic_configured) else ("rules_mode" if not is_agentic_configured else "success")

    return {
        "status": log.status,
        "risks_found_count": log.risks_found_count,
        "emails_sent": emails_sent,
        "summary": log.summary,
        "executed_at": log.executed_at.isoformat(),
        "result_source": result_source,
        "agent_status": agent_status,
        "latest_agent_run_id": latest_agent_run_id,
    }


@monitoring_router.get("/logs")
def list_monitoring_logs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MONITORING_VIEW)),
):
    """List historical execution runs of Agent 3."""
    logs = db.query(MonitoringExecutionLog).order_by(
        MonitoringExecutionLog.executed_at.desc()
    ).limit(limit).all()

    return [
        {
            "id": l.id,
            "cycle_type": l.cycle_type,
            "executed_at": l.executed_at.isoformat(),
            "status": l.status,
            "risks_found_count": l.risks_found_count,
            "summary": l.summary,
            "error_message": l.error_message,
        }
        for l in logs
    ]
