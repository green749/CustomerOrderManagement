from typing import Optional, List
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException, status, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..repositories.order_repo import OrderRepository
from ..services.order_service import OrderService
from ..services.cache_service import get_cached, set_cached, invalidate_cache
from ..schemas.common import PaginatedResponse
from ..schemas.order import (
    CustomerOrderListItem,
    CustomerOrderDetail,
    OrderTimelineResponse,
    AgentTimelineResponse,
    AgentTimelineItem,
)
from ..models.workflow import (
    OrderAssessment,
    RiskAlert,
    CommitmentProposal,
    AgentRun,
    AgentAction,
    OrderMonitoringRecord,
)
from ..models.auth import User
from ..services.auth_service import get_current_user
from ..security.permissions import require_permission, Permission
from ..services.promise_service import PromiseService
from ..schemas.promise import (
    ATPCheckResult,
    PromiseRecommendationResult,
)
from ..schemas.workflow import (
    CommitmentProposalCreate,
    CommitmentProposalResponse,
)
from ..services.workflow_service import WorkflowService
from ..services.kpi_service import KPIService
from ..schemas.kpis import (
    OverdueOrderItem,
    OrderStatusDraftResponse,
    EscalationPackResponse,
)

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.get("", response_model=PaginatedResponse[CustomerOrderListItem])
def get_orders(
    page: int = Query(default=1, ge=1, description="Page number starting at 1"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    search: Optional[str] = Query(default=None, description="Search by order ID, customer name, or product name"),
    status: Optional[str] = Query(default=None, description="Filter by status (e.g. DELIVERED, IN_PRODUCTION, OPEN)"),
    customer_id: Optional[str] = Query(default=None, description="Filter by customer ID (e.g. CUS-001)"),
    product_id: Optional[str] = Query(default=None, description="Filter by product ID (e.g. SPH-A15-128)"),
    priority: Optional[str] = Query(default=None, description="Filter by priority (HIGH, MEDIUM, LOW)"),
    start_date: Optional[date] = Query(default=None, description="Filter orders placed on or after this date"),
    end_date: Optional[date] = Query(default=None, description="Filter orders placed on or before this date"),
    sort_by: str = Query(default="order_date", description="Field to sort by"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order"),
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve customer orders with server-side pagination, sorting, search, filtering, and Redis caching."""
    # 1. Sanitize query params
    search_val = search if isinstance(search, str) else None
    status_val = status if isinstance(status, str) else None
    customer_id_val = customer_id if isinstance(customer_id, str) else None
    product_id_val = product_id if isinstance(product_id, str) else None
    priority_val = priority if isinstance(priority, str) else None

    # 2. Check Redis Cache
    scope_str = ":".join(sorted(current_user.customer_scope or []))
    cache_key = f"orders:list:{page}:{page_size}:{search_val}:{status_val}:{customer_id_val}:{product_id_val}:{priority_val}:{start_date}:{end_date}:{sort_by}:{sort_order}:{scope_str}"
    cached_payload = get_cached(cache_key)
    if cached_payload is not None:
        if response:
            response.headers["X-Cache"] = "HIT (Redis)"
        return cached_payload

    # 3. Database Fetch
    items, total = OrderService.get_orders(
        db=db,
        page=page,
        page_size=page_size,
        status=status_val,
        customer_id=customer_id_val,
        product_id=product_id_val,
        priority=priority_val,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order,
        customer_scope=current_user.customer_scope,
        search=search_val,
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    result = PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

    # 3. Store in Redis Cache (TTL = 120s)
    try:
        set_cached(cache_key, result.model_dump(), ttl_seconds=120)
        if response:
            response.headers["X-Cache"] = "MISS (Saved to Redis)"
    except Exception:
        pass

    return result


@router.get("/overdue", response_model=PaginatedResponse[OverdueOrderItem])
def get_overdue_orders(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ORDER_VIEW)),
):
    """
    Deliverable: Overdue order alerts.
    Retrieve open orders past their confirmed delivery date, sorted by days overdue.
    """
    items, total = KPIService.get_overdue_orders(
        db=db,
        page=page,
        page_size=page_size,
        customer_scope=current_user.customer_scope,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/summary", response_model=dict)
def get_orders_summary(
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lightweight summary endpoint for dashboard KPIs instead of fetching all orders.
    Cached in Redis for high-speed sub-millisecond retrieval.
    """
    scope_str = ":".join(sorted(current_user.customer_scope or []))
    cache_key = f"orders:summary:{scope_str}"
    cached = get_cached(cache_key)
    if cached is not None:
        if response:
            response.headers["X-Cache"] = "HIT (Redis)"
        return cached

    summary = OrderRepository.get_orders_summary(db, customer_scope=current_user.customer_scope)
    try:
        set_cached(cache_key, summary, ttl_seconds=120)
        if response:
            response.headers["X-Cache"] = "MISS (Saved to Redis)"
    except Exception:
        pass
    return summary


@router.get("/{order_id}", response_model=CustomerOrderDetail)
def get_order_detail(
    order_id: str,
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve detailed order information with customer, product, shipments, and risk evaluation (Redis cached)."""
    scope_str = ":".join(sorted(current_user.customer_scope or []))
    cache_key = f"orders:detail:{order_id}:{scope_str}"
    cached = get_cached(cache_key)
    if cached is not None:
        if response:
            response.headers["X-Cache"] = "HIT (Redis)"
        return cached

    order = OrderService.get_order_detail(db, order_id, customer_scope=current_user.customer_scope)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )

    try:
        set_cached(cache_key, order.model_dump(), ttl_seconds=120)
        if response:
            response.headers["X-Cache"] = "MISS (Saved to Redis)"
    except Exception:
        pass
    return order


@router.get("/{order_id}/timeline", response_model=OrderTimelineResponse)
def get_order_timeline(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve chronologically ordered events across customer order, production, and shipments."""
    timeline = OrderService.get_order_timeline(db, order_id, customer_scope=current_user.customer_scope)
    if not timeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer order '{order_id}' was not found",
        )
    return timeline


@router.get("/{order_id}/agent-timeline", response_model=AgentTimelineResponse)
def get_order_agent_timeline(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ORDER_VIEW)),
):
    """
    Retrieve unified chronological agent activity timeline for an order:
    - Agent 3 risk alerts (severity, department, source badge: AGENT vs RULES)
    - Reassessment actions (type, status, whether auto-executed or approved, result, and failures with the error message)
    - Agent 2 reassessment runs (link to reasoning steps)
    - The delivery verdict (on time, or delayed by N days vs promised date)
    - Every proposal revision with its status
    """
    order = OrderRepository.get_order_by_id(db, order_id, customer_scope=current_user.customer_scope)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer order '{order_id}' was not found",
        )

    alerts = db.query(RiskAlert).filter(RiskAlert.customer_order_id == order_id).all()
    actions = db.query(AgentAction).filter(AgentAction.customer_order_id == order_id).all()
    proposals = db.query(CommitmentProposal).filter(CommitmentProposal.customer_order_id == order_id).all()
    runs = db.query(AgentRun).filter(AgentRun.customer_order_id == order_id).all()

    prop_ids = [p.id for p in proposals]
    assessments = db.query(OrderAssessment).filter(
        (OrderAssessment.customer_order_id == order_id) |
        (OrderAssessment.customer_order_id == f"PRE-{order_id}") |
        (OrderAssessment.proposal_id.in_(prop_ids) if prop_ids else False)
    ).all()

    mon_rec = db.query(OrderMonitoringRecord).filter(OrderMonitoringRecord.customer_order_id == order_id).first()

    promised_date = None
    if mon_rec and mon_rec.approved_delivery_date:
        promised_date = str(mon_rec.approved_delivery_date)
    elif order.confirmed_delivery_date:
        promised_date = str(order.confirmed_delivery_date)
    elif order.requested_delivery_date:
        promised_date = str(order.requested_delivery_date)

    latest_revised_date = None
    latest_delay_days = 0
    latest_verdict = "ON_TIME"
    has_active_revised = False

    def _to_utc_naive(dt):
        if dt is None:
            return None
        if isinstance(dt, date) and not isinstance(dt, datetime):
            return datetime.combine(dt, datetime.min.time())
        if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    sorted_props = sorted(
        proposals,
        key=lambda p: (p.revision or 1, _to_utc_naive(p.created_at) or datetime.min),
        reverse=True,
    )
    if sorted_props:
        top_prop = sorted_props[0]
        latest_revised_date = str(top_prop.revised_estimated_date or top_prop.proposed_date)
        latest_delay_days = top_prop.delay_days or 0
        latest_verdict = top_prop.verdict or ("DELAYED" if latest_delay_days > 0 else "ON_TIME")
        if (top_prop.revision or 1) > 1 and top_prop.status == "PENDING":
            has_active_revised = True

    items: List[AgentTimelineItem] = []

    # Map Agent 3 Risk Alerts
    for al in alerts:
        items.append(AgentTimelineItem(
            id=f"alert-{al.id}",
            category="RISK_ALERT",
            timestamp=_to_utc_naive(al.detected_at),
            title=al.title,
            department=al.department,
            severity=al.severity,
            source=al.result_source or "RULES",
            status=al.status,
            description=al.description,
            delivery_impact=al.delivery_impact,
            recommended_action=al.recommended_action,
        ))

    # Map Reassessment Actions
    for act in actions:
        err = None
        if act.status == "FAILED" and isinstance(act.result, dict):
            err = act.result.get("error") or act.result.get("message")
        items.append(AgentTimelineItem(
            id=f"action-{act.id}",
            category="ACTION",
            timestamp=_to_utc_naive(act.executed_at or act.created_at),
            title=f"Agent Action: {act.action_type.replace('_', ' ')}",
            action_type=act.action_type,
            status=act.status,
            is_auto_executed=(not act.requires_approval),
            approved_by=str(act.approved_by) if act.approved_by else None,
            proposed_by=act.proposed_by,
            result=act.result if isinstance(act.result, dict) else None,
            error_message=err,
            linked_alert_id=act.alert_id,
        ))

    # Map AgentRuns
    for r in runs:
        items.append(AgentTimelineItem(
            id=f"run-{r.id}",
            category="AGENT_RUN",
            timestamp=_to_utc_naive(r.created_at),
            title=f"Agent Execution: {r.agent_name}",
            agent_name=r.agent_name,
            status=r.status,
            source="AGENT" if r.provider == "domo" else "RULES",
            steps_count=len(r.steps) if isinstance(r.steps, list) else 0,
            assessment_id=r.assessment_id,
        ))

    # Map Assessments
    for ass in assessments:
        items.append(AgentTimelineItem(
            id=f"assessment-{ass.id}",
            category="ASSESSMENT",
            timestamp=_to_utc_naive(ass.created_at),
            title=f"Feasibility Assessment ({ass.assessment_id})",
            assessment_id=ass.assessment_id,
            overall_status=ass.overall_status,
            source=ass.result_source or "RULES",
            estimated_delivery_date=str(ass.estimated_delivery_date) if ass.estimated_delivery_date else None,
            revised_estimated_date=str(ass.revised_estimated_date) if ass.revised_estimated_date else None,
            delay_days=ass.delay_days,
            verdict=ass.verdict,
            agent_reasoning=ass.agent_reasoning if isinstance(ass.agent_reasoning, list) else None,
            proposal_id=ass.proposal_id,
        ))

    # Map Proposals
    for p in proposals:
        items.append(AgentTimelineItem(
            id=f"proposal-{p.id}",
            category="PROPOSAL",
            timestamp=_to_utc_naive(p.created_at),
            title=f"Commitment Proposal Revision #{p.revision or 1}",
            revision=p.revision or 1,
            proposal_id=p.id,
            status=p.status,
            proposed_date=str(p.proposed_date) if p.proposed_date else None,
            revised_estimated_date=str(p.revised_estimated_date) if p.revised_estimated_date else None,
            delay_days=p.delay_days,
            verdict=p.verdict or ("DELAYED" if (p.delay_days and p.delay_days > 0) else "ON_TIME"),
            reasons=p.reasons if isinstance(p.reasons, list) else None,
            promised_date=promised_date,
        ))

    items.sort(key=lambda x: _to_utc_naive(x.timestamp) or datetime.min, reverse=True)

    return AgentTimelineResponse(
        customer_order_id=order_id,
        total_events=len(items),
        promised_date=promised_date,
        revised_estimated_date=latest_revised_date,
        delay_days=latest_delay_days,
        verdict=latest_verdict,
        has_active_revised_proposal=has_active_revised,
        events=items,
    )


@router.get("/{order_id}/atp-ctp", response_model=dict)
def get_order_atp_ctp(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ORDER_VIEW)),
):
    """Check ATP (materials availability) and CTP (capacity availability) for a customer order."""
    order = OrderRepository.get_order_by_id(db, order_id, customer_scope=current_user.customer_scope)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer order '{order_id}' was not found")

    try:
        atp = PromiseService.check_atp(db, order_id, order=order)
        ctp = PromiseService.check_ctp(db, order_id, order=order)
        return {
            "atp": atp.model_dump(),
            "ctp": ctp.model_dump(),
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/{order_id}/promise-recommendation", response_model=PromiseRecommendationResult)
def get_promise_recommendation(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ORDER_VIEW)),
):
    """Generate feasible promise-date recommendation with conflicts and transit buffer."""
    order = OrderRepository.get_order_by_id(db, order_id, customer_scope=current_user.customer_scope)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer order '{order_id}' was not found")

    try:
        return PromiseService.recommend_promise_date(db, order_id, order=order)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/{order_id}/commitment-proposals", response_model=CommitmentProposalResponse, status_code=status.HTTP_201_CREATED)
def create_commitment_proposal(
    order_id: str,
    body: CommitmentProposalCreate = CommitmentProposalCreate(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ORDER_CREATE)),
):
    """
    Create a commercial commitment proposal for an order in PENDING status.
    Uses feasible promise recommendation date if not specified.
    Increments revision for the order and records audit log.
    """
    try:
        return WorkflowService.create_commitment_proposal(
            db=db,
            customer_order_id=order_id,
            user=current_user,
            proposed_date=body.proposed_date,
            recommended_by=body.recommended_by,
            reasons=body.reasons,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get("/{order_id}/status-draft", response_model=OrderStatusDraftResponse)
def get_order_status_draft(
    order_id: str,
    polish: bool = Query(default=False, description="Whether to polish tone using Domo agent while preserving numbers"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ORDER_VIEW)),
):
    """
    Deliverable: Templated customer status update.
    Returns structured status, next milestone, promise date, and risks.
    Optional ?polish=true engages Domo agent to reword wording while strictly keeping numbers.
    """
    try:
        return KPIService.get_status_draft(
            db=db,
            customer_order_id=order_id,
            polish=polish,
            customer_scope=current_user.customer_scope,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))



@router.get("/{order_id}/escalation-pack", response_model=EscalationPackResponse)
def get_order_escalation_pack(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ORDER_VIEW)),
):
    """
    Deliverable: Account team escalation pack.
    Structured summary combining order, risks, ATP/CTP shortages, quality holds, shipment delays, proposed actions.
    """
    try:
        return KPIService.get_escalation_pack(
            db=db,
            customer_order_id=order_id,
            customer_scope=current_user.customer_scope,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/{order_id}/validation", response_model=dict)
def get_order_validation(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Slide 18: Order validation endpoint.
    Validates quantities, requested dates, ship-to, packaging, price and product configuration.
    """
    order = OrderRepository.get_order_by_id(db, order_id, customer_scope=current_user.customer_scope)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer order '{order_id}' was not found",
        )
    return OrderService.validate_order(order)



