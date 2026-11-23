import json
import queue
import threading
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, case
from sqlalchemy.orm import Session, selectinload, joinedload

from ..database import get_db, SessionLocal
from ..models.auth import User
from ..models.workflow import OrderAssessment, CommitmentProposal
from ..schemas.workflow import OrderAssessmentCreate, OrderAssessmentResponse, DepartmentReadinessResponse
from ..services.auth_service import get_current_user
from ..security.permissions import require_permission, Permission
from ..services.feasibility_service import FeasibilityService

feasibility_router = APIRouter(prefix="/api/assessments", tags=["Agent 2 - Order Feasibility & Commitment"])


def _stream_feasibility_execution(run_fn):
    """Run a feasibility assessment in a worker thread and yield real-time SSE progress events."""
    q: "queue.Queue[Optional[dict]]" = queue.Queue()

    def _progress(evt: dict):
        q.put(evt)

    def _worker():
        worker_db = SessionLocal()
        try:
            assessment = run_fn(worker_db, _progress)
            # Reload relationships so serialization includes customer, product, readiness_records, proposal
            loaded = (
                worker_db.query(OrderAssessment)
                .options(
                    joinedload(OrderAssessment.customer),
                    joinedload(OrderAssessment.product),
                    selectinload(OrderAssessment.readiness_records),
                    joinedload(OrderAssessment.proposal),
                )
                .filter(OrderAssessment.id == assessment.id)
                .first()
            ) or assessment
            serialized = OrderAssessmentResponse.model_validate(loaded).model_dump(mode="json")
            q.put({"event": "complete", "assessment": serialized})
        except Exception as exc:
            q.put({"event": "error", "detail": str(exc)})
        finally:
            worker_db.close()
            q.put(None)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    def _event_generator():
        while True:
            try:
                item = q.get(timeout=20.0)
            except queue.Empty:
                # Keep-alive heartbeat comment so proxies never close the stream
                yield ": keep-alive\n\n"
                continue
            if item is None:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@feasibility_router.post("/stream")
def assess_new_order_stream(
    payload: OrderAssessmentCreate,
    current_user: User = Depends(require_permission(Permission.ASSESSMENT_CREATE)),
):
    """
    AGENT 2 STREAMING TRIGGER: Runs all 7 department audits and real Domo AI Agent 2
    (strict_agent=True, no deterministic fallback) streaming real-time SSE events.
    """
    user_id = current_user.id

    def _run(worker_db: Session, progress_cb):
        worker_user = worker_db.query(User).filter(User.id == user_id).first()
        return FeasibilityService.assess_new_order(
            db=worker_db,
            customer_id=payload.customer_id,
            product_id=payload.product_id,
            order_qty=payload.order_qty,
            requested_delivery_date=payload.requested_delivery_date,
            user=worker_user,
            unit_price_inr=payload.unit_price_inr,
            priority=payload.priority,
            channel=payload.channel,
            ship_to=payload.ship_to,
            product_config=payload.product_config,
            packaging_req=payload.packaging_req,
            submit_for_approval=payload.submit_for_approval,
            progress_callback=progress_cb,
            strict_agent=True,
        )

    return _stream_feasibility_execution(_run)


@feasibility_router.post("", response_model=OrderAssessmentResponse, status_code=status.HTTP_201_CREATED)
def assess_new_order(
    payload: OrderAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSESSMENT_CREATE)),
):
    """
    AGENT 2 TRIGGER: Submit a new customer order for pre-confirmation feasibility assessment.
    Assesses ERP, MMS, MES, WMS, QMS, TMS, and PLM readiness, calculates achievable delivery date,
    and submits a proposal into the Approvals workflow for customer service review.
    """
    try:
        assessment = FeasibilityService.assess_new_order(
            db=db,
            customer_id=payload.customer_id,
            product_id=payload.product_id,
            order_qty=payload.order_qty,
            requested_delivery_date=payload.requested_delivery_date,
            user=current_user,
            unit_price_inr=payload.unit_price_inr,
            priority=payload.priority,
            channel=payload.channel,
            ship_to=payload.ship_to,
            product_config=payload.product_config,
            packaging_req=payload.packaging_req,
            submit_for_approval=payload.submit_for_approval,
        )
        return assessment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Assessment failed: {str(e)}")


@feasibility_router.get("/summary")
def get_assessments_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSESSMENT_VIEW)),
):
    """Return authoritative database aggregate KPI counts across all order assessments."""
    row = (
        db.query(
            func.count(OrderAssessment.id).label("total"),
            func.count(case((OrderAssessment.overall_status == "FEASIBLE", 1))).label("feasible"),
            func.count(
                case((OrderAssessment.overall_status.in_(["AT_RISK", "FEASIBLE_WITH_RISKS", "PARTIALLY_READY"]), 1))
            ).label("at_risk"),
            func.count(
                case((OrderAssessment.overall_status.in_(["NOT_FEASIBLE", "BLOCKED"]), 1))
            ).label("not_feasible"),
            func.count(case((CommitmentProposal.status == "PENDING", 1))).label("pending_approvals"),
        )
        .outerjoin(CommitmentProposal, OrderAssessment.proposal_id == CommitmentProposal.id)
        .one()
    )
    return {
        "total": int(row.total or 0),
        "feasible": int(row.feasible or 0),
        "at_risk": int(row.at_risk or 0),
        "not_feasible": int(row.not_feasible or 0),
        "pending_approvals": int(row.pending_approvals or 0),
    }


@feasibility_router.get("", response_model=List[OrderAssessmentResponse])
def list_assessments(
    customer_id: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    overall_status: Optional[str] = Query(None),
    customer_order_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=500),
    page: int = Query(1, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSESSMENT_VIEW)),
):
    """List recent order feasibility assessments with batched relationship loading."""
    effective_limit = page_size or limit
    q = db.query(OrderAssessment).options(
        joinedload(OrderAssessment.customer),
        joinedload(OrderAssessment.product),
        selectinload(OrderAssessment.readiness_records),
        joinedload(OrderAssessment.proposal),
    )
    if customer_id:
        q = q.filter(OrderAssessment.customer_id == customer_id)
    if product_id:
        q = q.filter(OrderAssessment.product_id == product_id)
    if overall_status:
        q = q.filter(OrderAssessment.overall_status == overall_status.upper())
    if customer_order_id:
        clean_oid = customer_order_id.replace("PRE-", "")
        q = q.filter(
            (OrderAssessment.customer_order_id == customer_order_id)
            | (OrderAssessment.customer_order_id == clean_oid)
            | (OrderAssessment.assessment_id == customer_order_id)
            | (OrderAssessment.assessment_id == clean_oid)
        )

    offset = (page - 1) * effective_limit if page > 1 else 0
    return q.order_by(OrderAssessment.created_at.desc()).offset(offset).limit(effective_limit).all()


@feasibility_router.get("/{assessment_id}", response_model=OrderAssessmentResponse)
def get_assessment(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSESSMENT_VIEW)),
):
    """Retrieve full details of an order feasibility assessment."""
    clean_id = assessment_id.replace("PRE-", "")
    assessment = db.query(OrderAssessment).options(
        joinedload(OrderAssessment.customer),
        joinedload(OrderAssessment.product),
        selectinload(OrderAssessment.readiness_records),
        joinedload(OrderAssessment.proposal),
    ).filter(
        (OrderAssessment.assessment_id == assessment_id)
        | (OrderAssessment.assessment_id == clean_id)
        | (OrderAssessment.customer_order_id == assessment_id)
        | (OrderAssessment.id == int(clean_id) if clean_id.isdigit() else False)
    ).first()

    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assessment '{assessment_id}' not found.")

    return assessment


@feasibility_router.get("/{assessment_id}/departments", response_model=List[DepartmentReadinessResponse])
def get_assessment_departments(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSESSMENT_VIEW)),
):
    """Retrieve department-level readiness breakdown for an assessment."""
    clean_id = assessment_id.replace("PRE-", "")
    assessment = db.query(OrderAssessment).filter(
        (OrderAssessment.assessment_id == assessment_id)
        | (OrderAssessment.assessment_id == clean_id)
        | (OrderAssessment.customer_order_id == assessment_id)
        | (OrderAssessment.id == int(clean_id) if clean_id.isdigit() else False)
    ).first()

    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assessment '{assessment_id}' not found.")

    return assessment.readiness_records


@feasibility_router.post("/{assessment_id}/reassess", response_model=OrderAssessmentResponse)
def reassess_order(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSESSMENT_CREATE)),
):
    """
    AGENT 2 TRIGGER: Re-evaluate feasibility and proposal for an existing order assessment.
    Runs the agentic feasibility loop with Domo LLM tool calling.
    """
    clean_id = assessment_id.replace("PRE-", "")
    existing = db.query(OrderAssessment).filter(
        (OrderAssessment.assessment_id == assessment_id)
        | (OrderAssessment.assessment_id == clean_id)
        | (OrderAssessment.customer_order_id == assessment_id)
        | (OrderAssessment.id == int(clean_id) if clean_id.isdigit() else False)
    ).first()

    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assessment '{assessment_id}' not found.")

    new_assessment = FeasibilityService.assess_new_order(
        db=db,
        customer_id=existing.customer_id,
        product_id=existing.product_id,
        order_qty=existing.order_qty,
        requested_delivery_date=existing.requested_delivery_date,
        user=current_user,
        unit_price_inr=float(existing.unit_price_inr) if existing.unit_price_inr is not None else None,
        priority=existing.priority,
        channel=existing.channel,
        ship_to=existing.ship_to,
        product_config=existing.product_config,
        packaging_req=existing.packaging_req,
        submit_for_approval=True,
    )
    return new_assessment


@feasibility_router.post("/{assessment_id}/reassess/stream")
def reassess_order_stream(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSESSMENT_CREATE)),
):
    """
    AGENT 2 STREAMING REASSESS TRIGGER: Re-evaluates all 7 departments and runs real Domo AI Agent 2
    (strict_agent=True, no deterministic fallback) streaming real-time SSE progress events.
    """
    clean_id = assessment_id.replace("PRE-", "")
    existing = db.query(OrderAssessment).filter(
        (OrderAssessment.assessment_id == assessment_id)
        | (OrderAssessment.assessment_id == clean_id)
        | (OrderAssessment.customer_order_id == assessment_id)
        | (OrderAssessment.id == int(clean_id) if clean_id.isdigit() else False)
    ).first()

    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assessment '{assessment_id}' not found.")

    snap = {
        "customer_id": existing.customer_id,
        "product_id": existing.product_id,
        "order_qty": existing.order_qty,
        "requested_delivery_date": existing.requested_delivery_date,
        "unit_price_inr": float(existing.unit_price_inr) if existing.unit_price_inr is not None else None,
        "priority": existing.priority,
        "channel": existing.channel,
        "ship_to": existing.ship_to,
        "product_config": existing.product_config,
        "packaging_req": existing.packaging_req,
    }
    user_id = current_user.id

    def _run(worker_db: Session, progress_cb):
        worker_user = worker_db.query(User).filter(User.id == user_id).first()
        return FeasibilityService.assess_new_order(
            db=worker_db,
            customer_id=snap["customer_id"],
            product_id=snap["product_id"],
            order_qty=snap["order_qty"],
            requested_delivery_date=snap["requested_delivery_date"],
            user=worker_user,
            unit_price_inr=snap["unit_price_inr"],
            priority=snap["priority"],
            channel=snap["channel"],
            ship_to=snap["ship_to"],
            product_config=snap["product_config"],
            packaging_req=snap["packaging_req"],
            submit_for_approval=True,
            progress_callback=progress_cb,
            strict_agent=True,
        )

    return _stream_feasibility_execution(_run)

