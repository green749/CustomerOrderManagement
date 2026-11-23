import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session, make_transient
from sqlalchemy import func

from ..config import settings
from ..models.business import FactCustomerOrder, FactProductionOrder, DimCustomer, DimProduct
from .agent_loop import run_agent_loop
from .prompts import AGENT_USER_PROMPT_TEMPLATE
from ..services.promise_service import (
    PromiseService,
    check_atp as svc_check_atp,
    check_ctp as svc_check_ctp,
    recommend_promise_date as svc_recommend_promise_date,
    propose_allocation as svc_propose_allocation,
)

logger = logging.getLogger("manufacturing.agent.feasibility")


def to_date(d: Any) -> Optional[date]:
    if d is None:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, datetime):
        return d.date()
    try:
        return datetime.strptime(str(d).split("T")[0].strip(), "%Y-%m-%d").date()
    except Exception:
        return None


# ------------------------------------------------------------------------------
# 1. FEASIBILITY AGENT SYSTEM PROMPT
# ------------------------------------------------------------------------------

FEASIBILITY_SYSTEM_PROMPT = """You are Agent 2: Order Feasibility & Commitment Agent for manufacturing operations.
Your role is to evaluate whether a new customer order demand is feasible across all 7 operational departments (ERP, MMS, MES, WMS, QMS, TMS, PLM), calculate the achievable delivery commitment date, and synthesize a commitment proposal.

CRITICAL RULES AND SEQUENCE CONSTRAINTS:
1. STRICT TRUTH & READ-ONLY: You must strictly use facts and data returned by the approved database tools. NEVER invent lead times, stock levels, or status codes.
2. MANDATORY FIRST STEP: You MUST call check_erp and check_plm FIRST.
3. EARLY STOPPING RULE: If check_erp returns readiness_status 'BLOCKED' or check_plm returns readiness_status 'BLOCKED', YOU MUST STOP IMMEDIATELY. Do not call any further department tools. Immediately return your final decision with overall_status 'NOT_FEASIBLE' and report the customer/product blocker.
4. FAST CONVERGENCE RULE: If ERP and PLM are not blocked, call 'audit_remaining_departments' to evaluate the remaining 5 departments (MMS, MES, WMS, QMS, TMS) and compute the achievable delivery date in one unified step. Do NOT loop through individual departments one by one. You MUST finalize your assessment within 4 steps.
5. EXACT GROUNDING ON DATES & STATUS: Your final JSON MUST strictly match the verified per_department_days, achievable_delivery_date, blockers, and computed_overall_status returned by audit_remaining_departments. NEVER report overall_status='FEASIBLE' when achievable_delivery_date is later than requested_delivery_date (days_variance > 0) or when any department has readiness_status 'BLOCKED', 'AT_RISK', or 'PARTIALLY_READY'.
6. NEVER SELF-APPROVE & NO AUTOMATIC APPROVAL: Your output is strictly a proposal for Human Customer Service review and approval. All customer orders require human approval; autonomous self-approval and automatic approvals are prohibited.
7. CONCISE THOUGHTS: Keep your "thought" field concise (1 to 2 sentences maximum) to preserve token space and ensure fast response times.
8. RESPONSE FORMAT: Strict JSON output format matching Agent 1 and Agent 3 schema. Always respond with ONE valid JSON object ONLY.

DECISION JSON SCHEMAS:

A. When calling an approved tool:
{{
  "thought": "Reasoning for selecting this tool (e.g. evaluating ERP commercial validation or PLM engineering readiness first)",
  "action": "<tool_name>",
  "input": {{<tool_arguments>}}
}}

B. When you have enough verified facts to deliver the final feasibility assessment:
{{
  "thought": "All 7 departments evaluated. No critical blockers detected. Critical path lead time is 6 days.",
  "action": "final",
  "confidence": "HIGH",
  "overall_status": "FEASIBLE",
  "estimated_delivery_date": "2026-11-25",
  "per_department_days": {{
    "ERP": 0,
    "MMS": 0,
    "MES": 1,
    "WMS": 1,
    "QMS": 1,
    "TMS": 3,
    "PLM": 0
  }},
  "blockers": [],
  "corrective_actions": [
    "Allocate production slot in next planning cycle (MMS responsibility)",
    "Sequence units across assembly lines (MES responsibility)",
    "Stage and reserve BOM raw materials (WMS responsibility)",
    "Execute standard post-production inspection and COA sign-off (QMS responsibility)",
    "Reserve carrier booking for transit (TMS responsibility)"
  ],
  "proposal_reasons": [
    "ERP commercial terms and credit verified.",
    "PLM active engineering revision confirmed.",
    "Achievable date calculated as 2026-11-25 based on 6 days critical path lead time."
  ],
  "answer": "The order is FEASIBLE for achievable delivery on 2026-11-25 with 6 days total critical path lead time."
}}

APPROVED FEASIBILITY TOOLS:
{tools}
"""


# ------------------------------------------------------------------------------
# 2. DEPARTMENT TOOLS & PROMISE TOOLS
# ------------------------------------------------------------------------------

def _build_transient_order(
    db: Session,
    order_context: Optional[Dict[str, Any]] = None,
    customer_id: Optional[str] = None,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    requested_delivery_date: Optional[Any] = None,
    unit_price_inr: Optional[float] = None,
    priority: Optional[str] = None,
    channel: Optional[str] = None,
    as_of_date: Optional[Any] = None,
    customer_order_id: Optional[str] = None,
    **kwargs: Any,
) -> FactCustomerOrder:
    ctx = order_context or {}
    cid = customer_id or ctx.get("customer_id")
    if not cid:
        c_row = db.query(DimCustomer.customer_id).first()
        cid = c_row[0] if c_row else "CUS-UNKNOWN"

    pid = product_id or ctx.get("product_id")
    if not pid:
        p_row = db.query(DimProduct.product_id).first()
        pid = p_row[0] if p_row else "PRD-UNKNOWN"

    qty = order_qty if order_qty is not None else ctx.get("order_qty")
    if qty is None:
        qty = 100

    ref_d = to_date(as_of_date) or to_date(ctx.get("as_of_date")) or settings.effective_reference_date or datetime.now().date()
    req_d = to_date(requested_delivery_date) or to_date(ctx.get("requested_delivery_date")) or (ref_d + timedelta(days=14))

    price = unit_price_inr if unit_price_inr is not None else ctx.get("unit_price_inr")
    if price is None:
        p_row = db.query(DimProduct.standard_unit_cost_inr).filter(DimProduct.product_id == pid).first()
        price = float(p_row[0]) if p_row and p_row[0] is not None else 0.0
    else:
        price = float(price)

    prio = priority or ctx.get("priority", "MEDIUM")
    chan = channel or ctx.get("channel", "EDI")
    oid = customer_order_id or ctx.get("customer_order_id") or "TEMP-FEASIBILITY"

    transient_order = FactCustomerOrder(
        customer_order_id=oid,
        customer_id=cid,
        product_id=pid,
        order_qty=qty,
        order_date=ref_d,
        requested_delivery_date=req_d,
        confirmed_delivery_date=req_d,
        shipped_qty=0,
        unit_price_inr=price,
        order_status="OPEN",
        priority=prio,
        channel=chan,
    )
    make_transient(transient_order)
    return transient_order


def tool_check_erp(
    db: Session,
    customer_id: Optional[str] = None,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    requested_delivery_date: Optional[str] = None,
    unit_price_inr: Optional[float] = None,
    as_of_date: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check Department 1: ERP / Commercial Sales & Credit Readiness."""
    ctx = order_context or {}
    pre = ctx.get("precomputed_readiness")
    if pre and isinstance(pre, dict) and "ERP" in pre:
        return dict(pre["ERP"])

    from ..services.feasibility_service import FeasibilityService
    cid = customer_id or ctx.get("customer_id") or ""
    pid = product_id or ctx.get("product_id") or ""
    qty = order_qty if order_qty is not None else ctx.get("order_qty", 100)
    ref_d = to_date(as_of_date) or to_date(ctx.get("as_of_date")) or settings.effective_reference_date or datetime.now().date()
    req_d = to_date(requested_delivery_date) or to_date(ctx.get("requested_delivery_date")) or (ref_d + timedelta(days=14))
    price = unit_price_inr if unit_price_inr is not None else ctx.get("unit_price_inr")
    res = FeasibilityService._assess_erp(
        db=db,
        customer_id=cid,
        product_id=pid,
        order_qty=qty,
        requested_delivery_date=req_d,
        unit_price_inr=price,
        ref_date=ref_d,
    )
    return res


def tool_check_plm(
    db: Session,
    product_id: Optional[str] = None,
    product_config: Optional[Dict[str, Any]] = None,
    as_of_date: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check Department 7: PLM – Product Lifecycle Management & BOM Engineering Readiness."""
    ctx = order_context or {}
    pre = ctx.get("precomputed_readiness")
    if pre and isinstance(pre, dict) and "PLM" in pre:
        return dict(pre["PLM"])

    from ..services.feasibility_service import FeasibilityService
    pid = product_id or ctx.get("product_id") or ""
    cfg = product_config if product_config is not None else ctx.get("product_config")
    ref_d = to_date(as_of_date) or to_date(ctx.get("as_of_date")) or settings.effective_reference_date or datetime.now().date()
    res = FeasibilityService._assess_plm(
        db=db,
        product_id=pid,
        product_config=cfg,
        ref_date=ref_d,
    )
    return res


def tool_check_mms(
    db: Session,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    as_of_date: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check Department 2: MMS – Manufacturing Management & Raw Material Availability."""
    ctx = order_context or {}
    pre = ctx.get("precomputed_readiness")
    if pre and isinstance(pre, dict) and "MMS" in pre:
        return dict(pre["MMS"])

    from ..services.feasibility_service import FeasibilityService
    pid = product_id or ctx.get("product_id") or ""
    qty = order_qty if order_qty is not None else ctx.get("order_qty", 100)
    ref_d = to_date(as_of_date) or to_date(ctx.get("as_of_date")) or settings.effective_reference_date or datetime.now().date()
    res = FeasibilityService._assess_mms(
        db=db,
        product_id=pid,
        order_qty=qty,
        ref_date=ref_d,
    )
    return res


def tool_check_mes(
    db: Session,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    requested_delivery_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check Department 3: MES – Manufacturing Execution System & Line Capacity."""
    ctx = order_context or {}
    pre = ctx.get("precomputed_readiness")
    if pre and isinstance(pre, dict) and "MES" in pre:
        return dict(pre["MES"])

    from ..services.feasibility_service import FeasibilityService
    pid = product_id or ctx.get("product_id") or ""
    qty = order_qty if order_qty is not None else ctx.get("order_qty", 100)
    ref_d = to_date(as_of_date) or to_date(ctx.get("as_of_date")) or settings.effective_reference_date or datetime.now().date()
    req_d = to_date(requested_delivery_date) or to_date(ctx.get("requested_delivery_date")) or (ref_d + timedelta(days=14))
    res = FeasibilityService._assess_mes(
        db=db,
        product_id=pid,
        order_qty=qty,
        ref_date=ref_d,
        requested_delivery_date=req_d,
    )
    return res


def tool_check_wms(
    db: Session,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    requested_delivery_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check Department 4: WMS – Warehouse Management & Staging Bay Readiness."""
    ctx = order_context or {}
    pre = ctx.get("precomputed_readiness")
    if pre and isinstance(pre, dict) and "WMS" in pre:
        return dict(pre["WMS"])

    from ..services.feasibility_service import FeasibilityService
    pid = product_id or ctx.get("product_id") or ""
    qty = order_qty if order_qty is not None else ctx.get("order_qty", 100)
    ref_d = to_date(as_of_date) or to_date(ctx.get("as_of_date")) or settings.effective_reference_date or datetime.now().date()
    res = FeasibilityService._assess_wms(
        db=db,
        product_id=pid,
        order_qty=qty,
        ref_date=ref_d,
    )
    return res


def tool_check_qms(
    db: Session,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    as_of_date: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check Department 5: QMS – Quality Management & Defect History."""
    ctx = order_context or {}
    pre = ctx.get("precomputed_readiness")
    if pre and isinstance(pre, dict) and "QMS" in pre:
        return dict(pre["QMS"])

    from ..services.feasibility_service import FeasibilityService
    pid = product_id or ctx.get("product_id") or ""
    qty = order_qty if order_qty is not None else ctx.get("order_qty", 100)
    ref_d = to_date(as_of_date) or to_date(ctx.get("as_of_date")) or settings.effective_reference_date or datetime.now().date()
    res = FeasibilityService._assess_qms(
        db=db,
        product_id=pid,
        order_qty=qty,
        ref_date=ref_d,
    )
    return res


def tool_check_tms(
    db: Session,
    customer_id: Optional[str] = None,
    ship_to: Optional[str] = None,
    priority: Optional[str] = None,
    requested_delivery_date: Optional[str] = None,
    order_qty: Optional[int] = None,
    as_of_date: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check Department 6: TMS – Transportation Management & Carrier Transit SLA."""
    ctx = order_context or {}
    pre = ctx.get("precomputed_readiness")
    if pre and isinstance(pre, dict) and "TMS" in pre:
        return dict(pre["TMS"])

    from ..services.feasibility_service import FeasibilityService
    cid = customer_id or ctx.get("customer_id") or ""
    ship = ship_to if ship_to is not None else ctx.get("ship_to")
    prio = priority or ctx.get("priority", "MEDIUM")
    qty = order_qty if order_qty is not None else ctx.get("order_qty", 100)
    ref_d = to_date(as_of_date) or to_date(ctx.get("as_of_date")) or settings.effective_reference_date or datetime.now().date()
    req_d = to_date(requested_delivery_date) or to_date(ctx.get("requested_delivery_date"))
    res = FeasibilityService._assess_tms(
        db=db,
        customer_id=cid,
        ship_to=ship,
        ref_date=ref_d,
        requested_delivery_date=req_d,
        order_qty=qty,
    )
    return res


def tool_check_atp(
    db: Session,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    customer_order_id: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check Available-to-Promise (ATP) material stocks and finished goods."""
    transient_order = _build_transient_order(
        db,
        order_context=order_context,
        product_id=product_id,
        order_qty=order_qty,
        customer_order_id=customer_order_id,
        **kwargs,
    )
    oid = customer_order_id or transient_order.customer_order_id or "PRE-TEMP"
    result = svc_check_atp(db, customer_order_id=oid, order=transient_order)
    return result.model_dump()


def tool_check_ctp(
    db: Session,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    customer_order_id: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check Capable-to-Promise (CTP) plant capacity and production line lead times."""
    transient_order = _build_transient_order(
        db,
        order_context=order_context,
        product_id=product_id,
        order_qty=order_qty,
        customer_order_id=customer_order_id,
        **kwargs,
    )
    oid = customer_order_id or transient_order.customer_order_id or "PRE-TEMP"
    result = svc_check_ctp(db, customer_order_id=oid, order=transient_order)
    return result.model_dump()


def tool_recommend_promise_date(
    db: Session,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    customer_id: Optional[str] = None,
    customer_order_id: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generate rule-based algorithmic promise date recommendation."""
    transient_order = _build_transient_order(
        db,
        order_context=order_context,
        customer_id=customer_id,
        product_id=product_id,
        order_qty=order_qty,
        customer_order_id=customer_order_id,
        **kwargs,
    )
    oid = customer_order_id or transient_order.customer_order_id or "PRE-TEMP"
    result = svc_recommend_promise_date(db, customer_order_id=oid, order=transient_order)
    return result.model_dump()


def tool_propose_allocation(
    db: Session,
    product_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Propose constrained inventory allocation across competing orders."""
    result = svc_propose_allocation(db, product_id=product_id)
    return result.model_dump()


def tool_get_competing_orders(
    db: Session,
    product_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Inspect active competing orders and plant production queue volume."""
    q = db.query(FactCustomerOrder).filter(
        FactCustomerOrder.order_status.in_(["OPEN", "IN_PRODUCTION", "HUMAN_APPROVAL", "CONFIRMED"])
    )
    if product_id:
        q = q.filter(FactCustomerOrder.product_id == product_id.strip().upper())
    
    competing = q.order_by(FactCustomerOrder.requested_delivery_date.asc()).limit(10).all()

    queue_stats = db.query(
        func.count(FactProductionOrder.production_order_id),
        func.sum(FactProductionOrder.order_qty),
    ).filter(FactProductionOrder.order_status.in_(["CREATED", "RELEASED", "IN_PROGRESS", "OPEN"])).first()

    return {
        "competing_orders_count": len(competing),
        "competing_orders_sample": [
            {
                "customer_order_id": o.customer_order_id,
                "customer_id": o.customer_id,
                "product_id": o.product_id,
                "order_qty": o.order_qty,
                "status": o.order_status,
                "requested_delivery_date": str(o.requested_delivery_date),
            }
            for o in competing
        ],
        "active_production_queue_orders": queue_stats[0] or 0 if queue_stats else 0,
        "active_production_queue_units": int(queue_stats[1] or 0) if queue_stats else 0,
    }


def tool_audit_remaining_departments(
    db: Session,
    product_id: Optional[str] = None,
    order_qty: Optional[int] = None,
    customer_id: Optional[str] = None,
    requested_delivery_date: Optional[str] = None,
    priority: Optional[str] = None,
    ship_to: Optional[str] = None,
    as_of_date: Optional[str] = None,
    order_context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Evaluates MMS, MES, WMS, QMS, TMS in one consolidated call to accelerate convergence.
    Returns readiness statuses, critical lead times, and calculated achievable delivery date.
    """
    ctx = order_context or {}
    pid = product_id or ctx.get("product_id") or ""
    qty = order_qty if order_qty is not None else ctx.get("order_qty", 100)
    cid = customer_id or ctx.get("customer_id") or ""
    req_d_val = requested_delivery_date or ctx.get("requested_delivery_date")
    prio = priority or ctx.get("priority", "MEDIUM")
    ship = ship_to if ship_to is not None else ctx.get("ship_to")
    ref_d = to_date(as_of_date) or to_date(ctx.get("as_of_date")) or settings.effective_reference_date or datetime.now().date()

    mms = tool_check_mms(db, product_id=pid, order_qty=qty, as_of_date=str(ref_d), order_context=order_context)
    mes = tool_check_mes(db, product_id=pid, order_qty=qty, requested_delivery_date=str(req_d_val) if req_d_val else None, as_of_date=str(ref_d), order_context=order_context)
    wms = tool_check_wms(db, product_id=pid, order_qty=qty, requested_delivery_date=str(req_d_val) if req_d_val else None, as_of_date=str(ref_d), order_context=order_context)
    qms = tool_check_qms(db, product_id=pid, order_qty=qty, as_of_date=str(ref_d), order_context=order_context)
    tms = tool_check_tms(db, customer_id=cid, ship_to=ship, priority=prio, requested_delivery_date=str(req_d_val) if req_d_val else None, order_qty=qty, as_of_date=str(ref_d), order_context=order_context)

    # Real lead times from verified department telemetry (estimated_delay_days)
    mms_days = int(mms.get("estimated_delay_days") or mms.get("estimated_component_lead_days") or 0)
    mes_days = int(mes.get("estimated_delay_days") or mes.get("estimated_production_days") or 1)
    wms_days = int(wms.get("estimated_delay_days") or wms.get("estimated_staging_days") or 1)
    qms_days = int(qms.get("estimated_delay_days") or qms.get("estimated_inspection_days") or 1)
    tms_days = int(tms.get("estimated_delay_days") or tms.get("estimated_transit_days") or 3)

    total_critical_lead_days = mms_days + mes_days + wms_days + qms_days + tms_days
    achievable_date = ref_d + timedelta(days=total_critical_lead_days)
    req_d = to_date(req_d_val)
    days_variance = (achievable_date - req_d).days if req_d else 0

    all_five = [mms, mes, wms, qms, tms]
    statuses = [d.get("readiness_status") for d in all_five]
    dept_blockers = [
        f"[{d.get('department')}] {d.get('identified_issue')}"
        for d in all_five if d.get("identified_issue")
    ]
    dept_actions = [
        f"[{d.get('department')}] {d.get('required_action')}"
        for d in all_five if d.get("required_action")
    ]

    if "BLOCKED" in statuses:
        computed_status = "NOT_FEASIBLE"
    elif "INSUFFICIENT_DATA" in statuses:
        computed_status = "INSUFFICIENT_DATA"
    elif days_variance <= 0 and all(s == "READY" for s in statuses):
        computed_status = "FEASIBLE"
    elif days_variance <= 3:
        computed_status = "FEASIBLE_WITH_RISKS"
    else:
        computed_status = "AT_RISK"

    def _compact_dept(d: Dict[str, Any]) -> Dict[str, Any]:
        ev = d.get("available_evidence")
        compact_ev = {}
        if isinstance(ev, dict):
            for k, v in ev.items():
                if k == "components" and isinstance(v, list):
                    shortages = [c for c in v if (c.get("shortage") or 0) > 0]
                    compact_ev["shortage_components"] = shortages[:5]
                    compact_ev["total_bom_components_checked"] = len(v)
                else:
                    compact_ev[k] = v
        return {
            "department": d.get("department"),
            "readiness_status": d.get("readiness_status"),
            "estimated_delay_days": d.get("estimated_delay_days", 0),
            "identified_issue": d.get("identified_issue"),
            "required_action": d.get("required_action"),
            "evidence": compact_ev,
        }

    return {
        "per_department_days": {
            "ERP": 0,
            "MMS": mms_days,
            "MES": mes_days,
            "WMS": wms_days,
            "QMS": qms_days,
            "TMS": tms_days,
            "PLM": 0,
        },
        "total_critical_path_days": total_critical_lead_days,
        "requested_delivery_date": str(req_d) if req_d else None,
        "achievable_delivery_date": str(achievable_date),
        "days_variance": days_variance,
        "computed_overall_status": computed_status,
        "overall_status": computed_status,
        "blockers": dept_blockers,
        "corrective_actions": dept_actions,
        "mms": _compact_dept(mms),
        "mes": _compact_dept(mes),
        "wms": _compact_dept(wms),
        "qms": _compact_dept(qms),
        "tms": _compact_dept(tms),
    }


FEASIBILITY_TOOLS = {
    "check_erp": tool_check_erp,
    "check_plm": tool_check_plm,
    "audit_remaining_departments": tool_audit_remaining_departments,
    "check_mms": tool_check_mms,
    "check_mes": tool_check_mes,
    "check_wms": tool_check_wms,
    "check_qms": tool_check_qms,
    "check_tms": tool_check_tms,
    "check_atp": tool_check_atp,
    "check_ctp": tool_check_ctp,
    "recommend_promise_date": tool_recommend_promise_date,
    "propose_allocation": tool_propose_allocation,
    "get_competing_orders": tool_get_competing_orders,
}

FEASIBILITY_TOOL_DESCRIPTIONS = """
- check_erp: Check Commercial Sales & Customer Credit readiness. MUST CALL FIRST.
  Args: {"customer_id": "CUS-XXX", "product_id": "SPH-XXX", "order_qty": 100, "requested_delivery_date": "YYYY-MM-DD"}
  Note: Verified order context parameters are auto-injected server-side.

- check_plm: Check Product Lifecycle Management & BOM Engineering readiness. MUST CALL FIRST.
  Args: {"product_id": "SPH-XXX"}
  Note: Verified order context parameters are auto-injected server-side.

- audit_remaining_departments: Check remaining 5 departments (MMS, MES, WMS, QMS, TMS) and calculate lead times in ONE step.
  Args: {"product_id": "SPH-XXX", "order_qty": 100, "customer_id": "CUS-XXX", "requested_delivery_date": "YYYY-MM-DD"}
  Note: Verified order context parameters are auto-injected server-side.

- check_mms: Check Material Management & raw component shortage readiness.
  Args: {"product_id": "SPH-XXX", "order_qty": 100}

- check_mes: Check Manufacturing Execution System line capacity and throughput.
  Args: {"product_id": "SPH-XXX", "order_qty": 100, "requested_delivery_date": "YYYY-MM-DD"}

- check_wms: Check Warehouse Management & staging bay readiness.
  Args: {"product_id": "SPH-XXX", "order_qty": 100, "requested_delivery_date": "YYYY-MM-DD"}

- check_qms: Check Quality Management, scrap rates, and inspection gate readiness.
  Args: {"product_id": "SPH-XXX", "order_qty": 100}

- check_tms: Check Transportation Management & carrier transit SLA readiness.
  Args: {"customer_id": "CUS-XXX", "ship_to": "..." | null, "priority": "HIGH" | "MEDIUM" | "LOW", "order_qty": 100, "requested_delivery_date": "YYYY-MM-DD"}

- check_atp: Check Available-to-Promise component inventory availability.
  Args: {"product_id": "SPH-XXX", "order_qty": 100}

- check_ctp: Check Capable-to-Promise plant assembly line lead times.
  Args: {"product_id": "SPH-XXX", "order_qty": 100}

- recommend_promise_date: Compute rule-based algorithmic achievable promise date.
  Args: {"customer_id": "CUS-XXX", "product_id": "SPH-XXX", "order_qty": 100}

- propose_allocation: Evaluate constrained inventory allocation across competing demand.
  Args: {"product_id": "SPH-XXX" | null}

- get_competing_orders: View active orders competing for plant capacity and queue volume.
  Args: {"product_id": "SPH-XXX" | null}
"""


# ------------------------------------------------------------------------------
# 3. PYDANTIC OUTPUT SCHEMA FOR AGENT 2
# ------------------------------------------------------------------------------

class FeasibilityAgentDecision(BaseModel):
    action: str = "final"
    thought: Optional[str] = None
    confidence: Optional[str] = "HIGH"
    overall_status: str = Field(..., description="FEASIBLE, FEASIBLE_WITH_RISKS, AT_RISK, NOT_FEASIBLE, INSUFFICIENT_DATA")
    estimated_delivery_date: Optional[date] = None
    per_department_days: Optional[Dict[str, int]] = Field(default_factory=dict)
    blockers: List[str] = Field(default_factory=list)
    corrective_actions: List[str] = Field(default_factory=list)
    proposal_reasons: List[str] = Field(default_factory=list)
    answer: Optional[str] = None

    @field_validator("overall_status", mode="before")
    @classmethod
    def validate_status(cls, v: Any) -> str:
        s = str(v).upper().strip() if v else "INSUFFICIENT_DATA"
        valid = {"FEASIBLE", "FEASIBLE_WITH_RISKS", "AT_RISK", "NOT_FEASIBLE", "INSUFFICIENT_DATA"}
        return s if s in valid else "INSUFFICIENT_DATA"

    @field_validator("estimated_delivery_date", mode="before")
    @classmethod
    def validate_date(cls, v: Any) -> Optional[date]:
        return to_date(v)


def normalize_feasibility_decision_dict(d: Any) -> Dict[str, Any]:
    """Normalize raw model decision dictionary into clean FeasibilityAgentDecision structure."""
    if not isinstance(d, dict):
        return {}

    norm = dict(d)

    # Unwrap nested answer / result / decision / final_answer wrappers
    for wrapper in ["answer", "result", "decision", "final_answer", "feasibility_assessment"]:
        if wrapper in norm:
            val = norm[wrapper]
            if isinstance(val, dict) and any(k in val for k in ["overall_status", "status", "estimated_delivery_date"]):
                for k, v in val.items():
                    if k not in norm or norm[k] is None:
                        norm[k] = v
            elif isinstance(val, str) and val.strip().startswith("{") and val.strip().endswith("}"):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict) and any(k in parsed for k in ["overall_status", "status", "estimated_delivery_date"]):
                        for k, v in parsed.items():
                            if k not in norm or norm[k] is None:
                                norm[k] = v
                except Exception:
                    pass

    # Normalize overall_status
    raw_status = str(norm.get("overall_status") or norm.get("status") or "").upper().strip()
    if "FEASIBLE_WITH_RISK" in raw_status:
        stat = "FEASIBLE_WITH_RISKS"
    elif "FEASIBLE" in raw_status and "NOT" not in raw_status and "RISK" not in raw_status:
        stat = "FEASIBLE"
    elif "NOT_FEASIBLE" in raw_status or "NOT FEASIBLE" in raw_status or "INFEASIBLE" in raw_status:
        stat = "NOT_FEASIBLE"
    elif "AT_RISK" in raw_status or "AT RISK" in raw_status or "RISK" in raw_status:
        stat = "AT_RISK"
    elif "INSUFFICIENT" in raw_status or "NO_DATA" in raw_status:
        stat = "INSUFFICIENT_DATA"
    else:
        stat = "FEASIBLE"
    norm["overall_status"] = stat

    # Normalize estimated_delivery_date
    raw_date = norm.get("estimated_delivery_date") or norm.get("promise_date") or norm.get("achievable_date") or norm.get("delivery_date")
    norm["estimated_delivery_date"] = to_date(raw_date)

    # Normalize per_department_days
    raw_days = norm.get("per_department_days") or norm.get("department_days") or {}
    norm_days: Dict[str, int] = {}
    if isinstance(raw_days, dict):
        for k, v in raw_days.items():
            k_upper = str(k).upper().strip()
            try:
                norm_days[k_upper] = int(v)
            except (ValueError, TypeError):
                pass
    norm["per_department_days"] = norm_days

    # Ensure list types
    for list_key in ["blockers", "corrective_actions", "proposal_reasons"]:
        val = norm.get(list_key)
        if isinstance(val, list):
            norm[list_key] = [str(x) for x in val if x]
        elif val:
            norm[list_key] = [str(val)]
        else:
            norm[list_key] = []

    if not norm.get("answer"):
        norm["answer"] = f"Feasibility status evaluated as {stat}."

    return norm


# ------------------------------------------------------------------------------
# 4. AGENT 2 RUNNER
# ------------------------------------------------------------------------------

def run_feasibility_agent(
    db: Session,
    customer_id: str,
    product_id: str,
    order_qty: int,
    requested_delivery_date: date,
    unit_price_inr: Optional[float] = None,
    priority: str = "MEDIUM",
    channel: str = "EDI",
    ship_to: Optional[str] = None,
    product_config: Optional[Dict[str, Any]] = None,
    as_of_date: Optional[date] = None,
    max_steps: int = 6,
    user_id: Optional[int] = None,
    monitoring_context: Optional[Dict[str, Any]] = None,
    customer_order_id: Optional[str] = None,
    precomputed_readiness: Optional[Dict[str, Any]] = None,
    step_callback: Optional[Any] = None,
) -> Tuple[Optional[FeasibilityAgentDecision], List[Dict[str, Any]], str]:
    """
    Runs Agent 2 ReAct feasibility assessment for a new customer demand.
    Returns: (decision_obj, steps, status)
    """
    from ..services.agent_controls_service import AgentControlsService

    # Validate customer_id and product_id exist in operational database
    cid_clean = customer_id.strip() if customer_id else ""
    pid_clean = product_id.strip() if product_id else ""

    pre_erp_ev = (precomputed_readiness or {}).get("ERP", {}).get("available_evidence") or {}
    if not pre_erp_ev.get("customer_found"):
        cust_exists = db.query(DimCustomer.customer_id).filter(DimCustomer.customer_id == cid_clean).first()
        if not cust_exists:
            logger.warning(f"Feasibility agent rejected: customer '{customer_id}' does not exist in DimCustomer.")
            return None, [], "invalid_order_data"

    if not pre_erp_ev.get("product_found"):
        prod_exists = db.query(DimProduct.product_id).filter(DimProduct.product_id == pid_clean).first()
        if not prod_exists:
            logger.warning(f"Feasibility agent rejected: product '{product_id}' does not exist in DimProduct.")
            return None, [], "invalid_order_data"

    # Check governor rate limit
    if not AgentControlsService.check_and_enforce_llm_call_limit(db, "agent2"):
        logger.warning("Agent 2 paused: hourly LLM call limit reached.")
        return None, [], "rate_limit_paused"

    ref_d = as_of_date or settings.effective_reference_date or datetime.now().date()
    ref_d_str = str(ref_d)
    req_d_str = str(requested_delivery_date) if requested_delivery_date else str(ref_d + timedelta(days=14))

    order_context = {
        "customer_id": cid_clean,
        "product_id": pid_clean,
        "order_qty": int(order_qty),
        "requested_delivery_date": req_d_str,
        "unit_price_inr": float(unit_price_inr) if unit_price_inr is not None else None,
        "priority": priority or "MEDIUM",
        "channel": channel or "EDI",
        "ship_to": ship_to,
        "product_config": product_config or {},
        "as_of_date": ref_d_str,
        "customer_order_id": customer_order_id,
        "precomputed_readiness": precomputed_readiness,
    }

    question = (
        f"Evaluate order feasibility for customer '{cid_clean}', product '{pid_clean}', "
        f"quantity {order_qty} units, requested delivery date {req_d_str}. "
        f"Priority: {priority}, Unit Price: {unit_price_inr} INR. "
        f"Reference as-of date: {ref_d_str}. "
        f"Note: Order-level fields (customer, product, quantity, delivery date, pricing) are automatically "
        f"supplied and verified server-side. "
        f"Mandatory rule: Call check_erp and check_plm first. If either is BLOCKED, STOP IMMEDIATELY."
    )

    if monitoring_context:
        question += (
            f"\n\nPRIOR MONITORING SURVEILLANCE CONTEXT (from Agent 3 Alert #{monitoring_context.get('alert_id')}):\n"
            f"Detected Risks: {json.dumps(monitoring_context.get('risks', []), default=str)}\n"
            f"Re-evaluate order feasibility taking these monitoring findings into account and re-verify facts with your tools."
        )

    all_steps = []
    try:
        AgentControlsService.record_llm_call("agent2")
        decision_dict, steps, provider, ai_available = run_agent_loop(
            db=db,
            question=question,
            history=[],
            max_steps=max_steps,
            user_id=user_id,
            system_prompt_template=FEASIBILITY_SYSTEM_PROMPT,
            user_prompt_template=AGENT_USER_PROMPT_TEMPLATE,
            tools=FEASIBILITY_TOOLS,
            tool_descriptions=FEASIBILITY_TOOL_DESCRIPTIONS,
            audit_entity="feasibility_agent",
            enable_deterministic_fallback=False,
            max_tokens=2200,
            temperature=0.1,
            return_dict=True,
            tool_context=order_context,
            step_callback=step_callback,
        )
        all_steps.extend(steps)
    except Exception as e:
        logger.warning(f"Error during run_agent_loop for feasibility agent: {e}", exc_info=True)
        return None, all_steps, "error"

    if not ai_available or provider != "domo_ai":
        return None, all_steps, provider

    # Grounding check: verify that check_erp was called.
    # If check_erp returned BLOCKED, early stopping is allowed and check_plm is not required.
    tools_called = [s.get("tool") for s in steps if s.get("tool")]
    erp_blocked = any(
        isinstance(s.get("output"), dict) and s.get("output", {}).get("readiness_status") == "BLOCKED"
        for s in steps if s.get("tool") == "check_erp"
    )
    if erp_blocked:
        grounding_ok = "check_erp" in tools_called
    else:
        grounding_ok = ("check_erp" in tools_called and "check_plm" in tools_called)

    if not grounding_ok:
        logger.warning(f"Feasibility agent grounding check failed: mandatory tools check_erp and check_plm not called ({tools_called}).")
        return None, all_steps, "validation_failed_twice"

    validation_err = None
    if not isinstance(decision_dict, dict):
        validation_err = f"Decision output is not a JSON object: {type(decision_dict)}"
    else:
        norm_dict = normalize_feasibility_decision_dict(decision_dict)
        try:
            decision_obj = FeasibilityAgentDecision.model_validate(norm_dict)
            return decision_obj, all_steps, "success"
        except Exception as val_err:
            validation_err = str(val_err)

    # REPAIR ATTEMPT: on validation or grounding failure, send model its own output + error without re-running all tools
    logger.info(f"Feasibility agent attempting repair due to validation/grounding error: {validation_err}")
    repair_prompt = (
        "You are Agent 2: Order Feasibility & Commitment Agent for manufacturing operations.\n"
        f"Your previous final assessment output failed schema validation with this error:\n"
        f"{validation_err}\n\n"
        f"Here was your previous response:\n"
        f"{json.dumps(decision_dict, default=str)[:1500]}\n\n"
        "Please fix the error and return ONLY ONE complete, valid JSON object matching the exact schema below.\n"
        "CRITICAL: The output MUST contain 'overall_status', 'estimated_delivery_date', 'per_department_days', and 'confidence' at the top level.\n"
        "{\n"
        '  "thought": "Concise summary of verified feasibility evidence",\n'
        '  "action": "final",\n'
        '  "confidence": "HIGH" | "MEDIUM" | "LOW",\n'
        '  "overall_status": "FEASIBLE" | "FEASIBLE_WITH_RISKS" | "AT_RISK" | "NOT_FEASIBLE" | "INSUFFICIENT_DATA",\n'
        '  "estimated_delivery_date": "YYYY-MM-DD",\n'
        '  "per_department_days": {"ERP": 0, "MMS": 0, "MES": 1, "WMS": 1, "QMS": 1, "TMS": 3, "PLM": 0},\n'
        '  "blockers": ["List of blockers or empty array"],\n'
        '  "corrective_actions": ["List of operational actions"],\n'
        '  "proposal_reasons": ["Concise reasons explaining achievable delivery date"],\n'
        '  "answer": "Feasibility assessment summary."\n'
        "}\n"
        "Respond ONLY with valid JSON."
    )

    try:
        from .domo_client import DomoTextLLM
        repair_llm = DomoTextLLM(max_tokens=2000, temperature=0.0)
        repair_raw = repair_llm.invoke(repair_prompt)
        from .agent_loop import _extract_json
        repair_dict = _extract_json(repair_raw)
        norm_repair = normalize_feasibility_decision_dict(repair_dict)
        decision_obj = FeasibilityAgentDecision.model_validate(norm_repair)
        logger.info("Feasibility agent repair attempt succeeded.")
        return decision_obj, all_steps, "success"
    except Exception as rep_err:
        logger.warning(f"FeasibilityAgentDecision repair attempt failed: {rep_err}")
        return None, all_steps, "validation_failed_twice"
