from typing import Dict, Any, List, Optional
import re
from decimal import Decimal
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from ..services.order_service import OrderService
from ..services.dashboard_service import DashboardService
from ..models.business import DimCustomer, FactCustomerOrder
from ..services.risk_service import OrderRiskAnalyzer


def resolve_customer(db: Session, identifier: Optional[str]) -> Optional[DimCustomer]:
    """
    Resolve a customer identifier (ID or Name) to an actual DimCustomer database record.
    Supported customers:
    - CUS-001 / Retailer North
    - CUS-002 / MobileMart
    - CUS-003 / Digital Bazaar
    - CUS-004 / Global Devices
    """
    if not identifier:
        return None
    clean = str(identifier).strip()
    if not clean:
        return None

    # 1. Exact or case-insensitive ID match
    cust = db.query(DimCustomer).filter(func.upper(DimCustomer.customer_id) == clean.upper()).first()
    if cust:
        return cust

    # 2. Case-insensitive substring match on customer name
    cust = db.query(DimCustomer).filter(DimCustomer.customer_name.ilike(f"%{clean}%")).first()
    if cust:
        return cust

    # 3. Strip common noise words (orders, summary, account, ltd, etc.)
    noise_stripped = re.sub(r"(?i)\b(orders?|summary|account|profile|performance|ltd|inc|corp|co)\b", "", clean).strip()
    if noise_stripped:
        cust = db.query(DimCustomer).filter(DimCustomer.customer_name.ilike(f"%{noise_stripped}%")).first()
        if cust:
            return cust

    return None


def tool_get_order_status(
    db: Session,
    customer_order_id: Optional[str] = None,
    order_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Retrieve current status, items, shipment milestones, and risk level for a customer order.
    Argument: customer_order_id (e.g. 'CO-000001')
    """
    raw_id = customer_order_id or order_id or kwargs.get("id")
    if not raw_id or not str(raw_id).strip():
        return {"error": "Please provide a valid customer_order_id (e.g. 'CO-000001')."}

    clean_id = str(raw_id).strip().upper()
    order_detail = OrderService.get_order_detail(db, clean_id)
    if not order_detail:
        return {"error": f"Customer order '{clean_id}' was not found in the database."}

    return {
        "customer_order_id": order_detail.customer_order_id,
        "customer_name": order_detail.customer_name,
        "product_name": order_detail.product_name,
        "order_status": order_detail.order_status,
        "priority": order_detail.priority,
        "order_date": str(order_detail.order_date),
        "requested_delivery_date": str(order_detail.requested_delivery_date),
        "confirmed_delivery_date": str(order_detail.confirmed_delivery_date),
        "order_qty": order_detail.order_qty,
        "shipped_qty": order_detail.shipped_qty,
        "total_value_inr": float(order_detail.total_value_inr),
        "risk_level": order_detail.risk.risk_level if order_detail.risk else "UNKNOWN",
        "risk_category": order_detail.risk.category if order_detail.risk else "UNKNOWN",
        "risk_reasons": order_detail.risk.reasons if order_detail.risk else [],
        "data_quality_warnings": order_detail.data_quality_warnings,
        "shipment_count": len(order_detail.shipments),
    }


def tool_list_at_risk_orders(
    db: Session,
    limit: Any = 10,
    risk_type: Optional[str] = None,
    risk_category: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    List orders currently identified as at risk of delay or having quality/quantity issues.
    Arguments:
      limit: Maximum number of orders to return (1-50, default 10)
      risk_type: Optional category filter ('ACTUAL_DELAY', 'POTENTIAL_DELAY', 'UNKNOWN_RISK')
    """
    try:
        int_limit = int(limit)
    except (ValueError, TypeError):
        int_limit = 10

    clamped_limit = min(max(1, int_limit), 50)
    category = risk_type or risk_category

    summary = DashboardService.get_at_risk_orders(
        db,
        page=1,
        page_size=clamped_limit,
        risk_category=category,
    )

    items = []
    for item in summary.items:
        items.append({
            "customer_order_id": item.customer_order_id,
            "customer_name": item.customer_name,
            "product_name": item.product_name,
            "order_status": item.order_status,
            "priority": item.priority,
            "confirmed_delivery_date": item.confirmed_delivery_date,
            "risk_level": item.risk.risk_level,
            "risk_category": item.risk.category,
            "reasons": item.risk.reasons,
        })

    return {
        "total_at_risk": summary.total_at_risk,
        "actual_delayed": summary.actual_delayed,
        "potential_delayed": summary.potential_delayed,
        "unknown_risk": summary.unknown_risk,
        "count_returned": len(items),
        "orders": items,
    }


def tool_get_customer_summary(
    db: Session,
    customer_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Get customer order history summary, active order volume, and fulfillment statistics.
    Argument: customer_id (e.g. 'CUS-001') or customer_name (e.g. 'Digital Bazaar')
    """
    raw_query = customer_id or customer_name or kwargs.get("name") or kwargs.get("id")
    if not raw_query or not str(raw_query).strip():
        return {
            "error": "Please provide a valid customer_id (e.g. 'CUS-001') or customer name "
                     "(e.g. 'Digital Bazaar', 'Retailer North', 'MobileMart', 'Global Devices')."
        }

    customer = resolve_customer(db, str(raw_query).strip())
    if not customer:
        return {
            "error": f"Customer '{raw_query}' was not found in the database. "
                     "Available customers in system: CUS-001 (Retailer North), CUS-002 (MobileMart), "
                     "CUS-003 (Digital Bazaar), CUS-004 (Global Devices)."
        }

    orders = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_id == customer.customer_id).all()
    total_orders = len(orders)
    delivered = sum(1 for o in orders if o.order_status == "DELIVERED")
    open_orders = sum(1 for o in orders if o.order_status in ("OPEN", "CONFIRMED", "IN_PRODUCTION"))
    total_value = sum(Decimal(o.order_qty) * Decimal(o.unit_price_inr) for o in orders)

    return {
        "customer_id": customer.customer_id,
        "customer_name": customer.customer_name,
        "segment": customer.segment,
        "country": customer.country,
        "service_level": customer.service_level,
        "preferred_carrier": customer.preferred_carrier,
        "total_orders": total_orders,
        "delivered_orders": delivered,
        "open_orders": open_orders,
        "fulfillment_rate_pct": round((delivered / total_orders * 100), 2) if total_orders > 0 else 0.0,
        "total_order_value_inr": float(total_value),
    }


def tool_get_order_delay_analysis(
    db: Session,
    customer_order_id: Optional[str] = None,
    order_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Perform deep root-cause delay and discrepancy analysis for a specific customer order.
    Argument: customer_order_id (e.g. 'CO-000001')
    """
    raw_id = customer_order_id or order_id or kwargs.get("id")
    if not raw_id or not str(raw_id).strip():
        return {"error": "Please provide a valid customer_order_id (e.g. 'CO-000001')."}

    clean_id = str(raw_id).strip().upper()
    order_detail = OrderService.get_order_detail(db, clean_id)
    if not order_detail:
        return {"error": f"Customer order '{clean_id}' was not found in the database."}

    # Evaluate timeline and milestones
    timeline = OrderService.get_order_timeline(db, clean_id)

    milestone_delays = []
    shipment_details = []
    for s in order_detail.shipments:
        ship_info = {
            "shipment_id": s.shipment_id,
            "carrier": s.carrier,
            "vehicle_type": s.vehicle_type,
            "shipment_status": s.shipment_status,
            "planned_eta": str(s.planned_eta),
            "actual_delivery_ts": str(s.actual_delivery_ts) if s.actual_delivery_ts else None,
            "freight_cost_inr": float(s.freight_cost_inr) if s.freight_cost_inr else 0.0,
        }
        shipment_details.append(ship_info)
        if s.shipment_status == "DELAYED":
            milestone_delays.append(ship_info)

    # Inspect linked production and quality checks
    quality_notes = []
    for po in order_detail.production_orders:
        po_id = po.get("production_order_id") if isinstance(po, dict) else getattr(po, "production_order_id", "PO")
        po_status = po.get("order_status") or po.get("status") if isinstance(po, dict) else (getattr(po, "order_status", None) or getattr(po, "status", None))
        if po_status == "HOLD":
            quality_notes.append(f"Production order {po_id} is on HOLD.")

    return {
        "customer_order_id": clean_id,
        "customer_name": order_detail.customer_name,
        "product_name": order_detail.product_name,
        "order_status": order_detail.order_status,
        "priority": order_detail.priority,
        "requested_delivery_date": str(order_detail.requested_delivery_date),
        "confirmed_delivery_date": str(order_detail.confirmed_delivery_date),
        "delay_category": order_detail.risk.category if order_detail.risk else "UNKNOWN",
        "risk_level": order_detail.risk.risk_level if order_detail.risk else "UNKNOWN",
        "delay_reasons": order_detail.risk.reasons if order_detail.risk else [],
        "data_quality_warnings": order_detail.data_quality_warnings,
        "transit_delay_milestones": milestone_delays,
        "all_shipment_milestones": shipment_details,
        "order_qty": order_detail.order_qty,
        "shipped_qty": order_detail.shipped_qty,
        "quantity_match": order_detail.order_qty == order_detail.shipped_qty,
        "has_linked_production_orders": len(order_detail.production_orders) > 0,
        "quality_notes": quality_notes,
        "timeline_events_count": timeline.total_events if timeline else 0,
    }


def tool_get_inventory_availability(
    db: Session,
    material_id: Optional[str] = None,
    product_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Check actual warehouse inventory, on-hand stock, blocked units, and quality holds."""
    # 1. Query Agent 09 Inventory Management database (Live, Strictly Read-Only)
    try:
        from ..services.agent_db_service import AgentDatabaseService
        live_items = AgentDatabaseService.check_live_material_availability(material_id)
        if live_items:
            return {
                "source": "AGENT_09_INVENTORY_DB (Inventory Management Lead · Read-Only)",
                "count": len(live_items),
                "items": live_items,
            }
    except Exception:
        pass

    # 2. Local fallback to internal database snapshots
    from ..models.business import FactInventoryDailySnapshot
    from ..models.operational import DimMaterial
    q = db.query(FactInventoryDailySnapshot)
    if material_id:
        q = q.filter(FactInventoryDailySnapshot.material_id.ilike(f"%{material_id.strip()}%"))
    latest_date = db.query(func.max(FactInventoryDailySnapshot.snapshot_date)).scalar()
    if latest_date:
        q = q.filter(FactInventoryDailySnapshot.snapshot_date == latest_date)
    records = q.limit(20).all()
    if not records:
        return {"message": f"No inventory records found for material/product query.", "items": []}
    
    items = []
    for r in records:
        mat = db.query(DimMaterial).filter(DimMaterial.material_id == r.material_id).first()
        items.append({
            "material_id": r.material_id,
            "material_name": mat.material_name if mat else r.material_id,
            "warehouse_id": r.warehouse_id,
            "lot_id": r.lot_id,
            "on_hand_qty": r.on_hand_qty,
            "allocated_qty": r.allocated_qty,
            "blocked_qty": r.blocked_qty,
            "quality_hold_qty": r.quality_hold_qty,
            "usable_qty": max(0, r.on_hand_qty - r.allocated_qty - r.blocked_qty - r.quality_hold_qty),
            "status": r.inventory_status,
            "source": "LOCAL_WAREHOUSE_SNAPSHOT",
        })
    return {"as_of_date": str(latest_date), "count": len(items), "items": items}


def tool_get_production_progress(
    db: Session,
    customer_order_id: Optional[str] = None,
    production_order_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieve actual shop-floor production order status, planned dates, and quality gates."""
    from ..models.business import FactProductionOrder, FactQualityInspection
    cid = customer_order_id or kwargs.get("id")
    pid = production_order_id
    q = db.query(FactProductionOrder)
    if pid:
        q = q.filter(FactProductionOrder.production_order_id == pid.strip().upper())
    elif cid:
        clean_cid = cid.strip().upper()
        q = q.filter(FactProductionOrder.customer_order_id == clean_cid)
    
    pos = q.limit(10).all()
    if not pos:
        return {"error": f"No production orders found matching query."}
    
    results = []
    for p in pos:
        insp_count = db.query(func.count(FactQualityInspection.inspection_id)).filter(
            FactQualityInspection.production_order_id == p.production_order_id
        ).scalar() or 0
        results.append({
            "production_order_id": p.production_order_id,
            "product_id": p.product_id,
            "customer_order_id": p.customer_order_id,
            "order_qty": p.order_qty,
            "status": p.order_status,
            "planned_start": str(p.planned_start),
            "planned_finish": str(p.planned_finish),
            "due_date": str(p.due_date),
            "inspections_logged": insp_count,
        })
    return {"production_orders": results}


def tool_get_transportation_status(
    db: Session,
    customer_order_id: Optional[str] = None,
    shipment_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieve real carrier transit milestones, tracking status, and delivery dates."""
    from ..models.business import FactShipmentMilestone
    cid = customer_order_id or kwargs.get("id")
    sid = shipment_id
    q = db.query(FactShipmentMilestone)
    if sid:
        q = q.filter(FactShipmentMilestone.shipment_id == sid.strip().upper())
    elif cid:
        q = q.filter(FactShipmentMilestone.customer_order_id == cid.strip().upper())
    
    shipments = q.limit(10).all()
    if not shipments:
        return {"message": "No active shipment milestones recorded for this query."}
    
    items = []
    for s in shipments:
        items.append({
            "shipment_id": s.shipment_id,
            "customer_order_id": s.customer_order_id,
            "carrier": s.carrier,
            "vehicle_type": s.vehicle_type,
            "status": s.shipment_status,
            "dispatch_date": str(s.dispatch_date),
            "planned_eta": str(s.planned_eta),
            "actual_delivery_ts": str(s.actual_delivery_ts) if s.actual_delivery_ts else None,
            "pod_status": s.pod_status,
        })
    return {"shipments": items}


def tool_get_quality_and_genealogy(
    db: Session,
    customer_order_id: Optional[str] = None,
    production_order_id: Optional[str] = None,
    product_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Query live Agent 08 Quality & Product Traceability database for real-time
    quality inspections (dispositions, holds, scraps), open NCR/CAPA investigations,
    and product genealogy events.
    """
    from ..services.agent_db_service import AgentDatabaseService
    from ..models.business import FactProductionOrder, FactCustomerOrder

    po_ids = []
    if production_order_id and str(production_order_id).strip():
        po_ids.append(str(production_order_id).strip().upper())

    clean_cid = str(customer_order_id).strip().upper() if customer_order_id else None
    derived_pid = str(product_id).strip().upper() if product_id else None

    if clean_cid:
        pos = db.query(FactProductionOrder).filter(
            FactProductionOrder.customer_order_id == clean_cid
        ).all()
        for p in pos:
            if p.production_order_id and p.production_order_id not in po_ids:
                po_ids.append(p.production_order_id)
        if not derived_pid:
            order = db.query(FactCustomerOrder).filter(
                FactCustomerOrder.customer_order_id == clean_cid
            ).first()
            if order and order.product_id:
                derived_pid = order.product_id

    records = AgentDatabaseService.get_quality_and_genealogy_for_orders(
        production_order_ids=po_ids,
        product_id=derived_pid,
    )

    return {
        "customer_order_id": clean_cid,
        "production_order_ids": po_ids,
        "product_id": derived_pid,
        "connected": records.get("connected", False),
        "inspections": records.get("inspections", []),
        "ncrs": records.get("ncrs", []),
        "genealogy_events": records.get("genealogy_events", []),
        "data_source": "AGENT_08_QUALITY_TRACEABILITY_LIVE_NEON_DB",
    }


AVAILABLE_TOOLS = {
    "get_order_status": tool_get_order_status,
    "list_at_risk_orders": tool_list_at_risk_orders,
    "get_customer_summary": tool_get_customer_summary,
    "get_order_delay_analysis": tool_get_order_delay_analysis,
    "get_inventory_availability": tool_get_inventory_availability,
    "get_production_progress": tool_get_production_progress,
    "get_transportation_status": tool_get_transportation_status,
    "get_quality_and_genealogy": tool_get_quality_and_genealogy,
}

TOOL_DESCRIPTIONS = """
- get_order_status: Retrieve current status, item, customer, shipment count, and risk rating for an order.
  Args: {"customer_order_id": "CO-XXXXXX"}

- list_at_risk_orders: List orders with actual delivery delays, potential delivery risks, or data inconsistencies.
  Args: {"limit": 10, "risk_type": "ACTUAL_DELAY" | "POTENTIAL_DELAY" | "UNKNOWN_RISK" | null}

- get_customer_summary: View customer profile, order volume, and fulfillment metrics by customer ID or customer name.
  Args: {"customer_id": "CUS-XXX" or "Customer Name"}

- get_order_delay_analysis: Detailed root-cause breakdown of delay reasons, carrier transit milestones, and quality holds.
  Args: {"customer_order_id": "CO-XXXXXX"}

- get_inventory_availability: Check current on-hand warehouse inventory, usable stock, and quality holds for materials.
  Args: {"material_id": "MAT-XXX" | null}

- get_production_progress: Retrieve shop-floor production order status, scheduled line execution, and quality inspection count.
  Args: {"customer_order_id": "CO-XXXXXX" | null, "production_order_id": "PO-XXXXXX" | null}

- get_transportation_status: Check carrier transit milestones, planned ETA, and proof of delivery status.
  Args: {"customer_order_id": "CO-XXXXXX" | null, "shipment_id": "SHP-XXXXXX" | null}

- get_quality_and_genealogy: Check live Agent 08 quality inspection holds, open NCR/CAPA investigations, and genealogy events.
  Args: {"customer_order_id": "CO-XXXXXX" | null, "production_order_id": "PO-XXXXXX" | null, "product_id": "SPH-XXX" | null}
"""

