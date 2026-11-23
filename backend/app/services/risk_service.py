from datetime import date, datetime
from typing import Dict, Any, List, Optional
from ..config import settings
from ..models.business import FactCustomerOrder, FactShipmentMilestone, FactProductionOrder
from ..schemas.order import OrderRiskInfo

# Default reference date for the dataset (orders range Aug 2026 - Nov 2026)
REFERENCE_DATE = settings.effective_reference_date


def derive_release_status(inspections: List[Any]) -> str:
    """
    Derive quality release_status from inspection dispositions:
    - RELEASED: All inspections have disposition == 'RELEASE' (and at least 1 inspection)
    - ON_HOLD: Any inspection has disposition == 'HOLD'
    - REWORK: Any inspection has disposition == 'REWORK' (if no HOLD)
    - SCRAPPED: Any inspection has disposition == 'SCRAP' (if no HOLD or REWORK)
    - NOT_INSPECTED: No inspections recorded
    """
    if not inspections:
        return "NOT_INSPECTED"

    dispositions = {getattr(i, "disposition", "").upper() for i in inspections}
    if "HOLD" in dispositions:
        return "ON_HOLD"
    if "REWORK" in dispositions:
        return "REWORK"
    if "SCRAP" in dispositions:
        return "SCRAPPED"
    if dispositions == {"RELEASE"}:
        return "RELEASED"
    return "RELEASED" if "RELEASE" in dispositions else "NOT_INSPECTED"


class OrderRiskAnalyzer:
    """
    Transparent, rule-based risk analyzer for customer orders.
    Distinguishes:
    - ACTUAL_DELAY: Confirmed delivery date passed without delivery, or delivered late
    - POTENTIAL_DELAY: Indicators that upcoming delivery is at risk
    - UNKNOWN_RISK: Insufficient data or missing links
    - ON_SCHEDULE: Satisfies delivery commitments
    """

    @staticmethod
    def evaluate_order(
        order: FactCustomerOrder,
        shipments: Optional[List[FactShipmentMilestone]] = None,
        production_orders: Optional[List[FactProductionOrder]] = None,
        as_of_date: Optional[date] = None,
        link_type: str = "DIRECT",
        link_confidence: Optional[str] = None,
    ) -> OrderRiskInfo:
        current_date = as_of_date or settings.effective_reference_date
        reasons: List[str] = []
        warnings: List[str] = []
        
        category = "ON_SCHEDULE"
        risk_level = "LOW"

        # 1. Check Production Linkage & Heuristic Transparency
        has_production_order = production_orders is not None and len(production_orders) > 0
        if not has_production_order:
            warnings.append("Missing production link: No production order linked to this customer order in manufacturing execution records.")
            if order.order_status in ("OPEN", "CONFIRMED", "IN_PRODUCTION"):
                category = "UNKNOWN_RISK"
                reasons.append("Unknown production risk: Order is active but has no associated production order records to verify manufacturing progress.")
                risk_level = "MEDIUM"
        elif link_type == "INFERRED":
            warnings.append(
                f"Production link inferred via heuristic ({link_confidence} confidence): "
                f"matched {len(production_orders)} production order(s) by product and due date proximity."
            )

        # 2. Check Shipment & Quantity Inconsistencies
        shipment_list = shipments or []
        total_milestone_qty = sum(s.shipment_qty for s in shipment_list)

        if order.shipped_qty > order.order_qty:
            reasons.append(f"Quantity inconsistency: shipped quantity ({order.shipped_qty}) exceeds order quantity ({order.order_qty}).")
            category = "POTENTIAL_DELAY" if category == "ON_SCHEDULE" else category
            risk_level = "HIGH"

        # Rule 4: Delivered with shortfall in synthetic data
        # Treat DELIVERED + shipped_qty < order_qty as DATA_QUALITY warning unless shipment milestones prove an active shortfall
        if order.order_status == "DELIVERED":
            if order.shipped_qty < order.order_qty:
                warnings.append(
                    f"Data quality warning: Order status is DELIVERED but recorded shipped quantity is {order.shipped_qty} of {order.order_qty} units."
                )
                # Check if shipment milestones show explicit delivery issues
                undelivered_milestones = [s for s in shipment_list if s.shipment_status != "DELIVERED"]
                if undelivered_milestones:
                    reasons.append(f"Partial fulfillment confirmed: {len(undelivered_milestones)} milestone(s) not delivered.")
                    category = "ACTUAL_DELAY"
                    risk_level = "CRITICAL" if order.priority == "HIGH" else "HIGH"

        if shipment_list and total_milestone_qty != order.shipped_qty:
            warnings.append(f"Milestone mismatch: sum of shipment milestones ({total_milestone_qty}) differs from order shipped quantity ({order.shipped_qty}).")

        # 3. Check Delivery Date Performance (Actual vs Confirmed)
        confirmed_date = order.confirmed_delivery_date
        
        # Check shipment milestones for actual deliveries or transit delays
        delivered_shipments = [s for s in shipment_list if s.shipment_status == "DELIVERED" and s.actual_delivery_ts]
        delayed_shipments = [s for s in shipment_list if s.shipment_status == "DELAYED"]
        in_transit_shipments = [s for s in shipment_list if s.shipment_status == "IN_TRANSIT"]

        if delayed_shipments:
            reasons.append(f"{len(delayed_shipments)} shipment milestone(s) reported as DELAYED in transit carrier tracking.")
            category = "ACTUAL_DELAY"
            risk_level = "CRITICAL" if order.priority == "HIGH" else "HIGH"

        if order.order_status == "DELIVERED":
            # Check if any shipment arrived after confirmed delivery date
            late_deliveries = []
            for s in delivered_shipments:
                actual_date = s.actual_delivery_ts.date() if isinstance(s.actual_delivery_ts, datetime) else s.actual_delivery_ts
                if actual_date > confirmed_date:
                    days_late = (actual_date - confirmed_date).days
                    late_deliveries.append((s.shipment_id, days_late))
            
            if late_deliveries:
                category = "ACTUAL_DELAY"
                risk_level = "MEDIUM"  # Historical delivery delay
                reasons.append(f"Historical late delivery: {len(late_deliveries)} shipment(s) delivered after confirmed date (up to {max(d[1] for d in late_deliveries)} days late).")
            else:
                if not reasons:
                    category = "ON_SCHEDULE"
                    risk_level = "LOW"
                    reasons.append("Order fulfilled and delivered on schedule.")

        else:
            # Order is NOT delivered yet
            if confirmed_date < current_date:
                # Past due date!
                days_overdue = (current_date - confirmed_date).days
                category = "ACTUAL_DELAY"
                reasons.append(f"Overdue delivery: Confirmed date was {confirmed_date} ({days_overdue} days past target). Current status is {order.order_status}.")
                risk_level = "CRITICAL" if order.priority in ("HIGH", "CRITICAL") else "HIGH"
            
            elif confirmed_date == current_date:
                if order.order_status in ("OPEN", "CONFIRMED", "IN_PRODUCTION"):
                    category = "POTENTIAL_DELAY"
                    reasons.append(f"Delivery due today ({confirmed_date}) but order is currently in '{order.order_status}' status.")
                    risk_level = "CRITICAL" if order.priority == "HIGH" else "HIGH"
            
            else:
                # Due date is in future
                days_until_due = (confirmed_date - current_date).days
                
                # Check for in-transit shipments ETA vs confirmed date
                for s in in_transit_shipments:
                    eta_date = s.planned_eta.date() if isinstance(s.planned_eta, datetime) else s.planned_eta
                    if eta_date > confirmed_date:
                        category = "POTENTIAL_DELAY"
                        days_slip = (eta_date - confirmed_date).days
                        reasons.append(f"Carrier planned ETA ({eta_date}) is {days_slip} days after customer confirmed date ({confirmed_date}).")
                        risk_level = "HIGH" if order.priority == "HIGH" else "MEDIUM"

                if days_until_due <= 3 and order.order_status in ("OPEN", "CONFIRMED"):
                    category = "POTENTIAL_DELAY"
                    reasons.append(f"Urgent timeline: Due in {days_until_due} days but order has not reached production or dispatch stage.")
                    risk_level = "HIGH" if order.priority == "HIGH" else "MEDIUM"
                
                elif not reasons:
                    category = "ON_SCHEDULE"
                    risk_level = "LOW"
                    reasons.append(f"On schedule for delivery on {confirmed_date}.")

        # 4. Check Quality Concerns and Release Status if production order linked
        if has_production_order and production_orders:
            all_inspections = []
            for po in production_orders:
                if hasattr(po, "inspections") and po.inspections:
                    all_inspections.extend(po.inspections)

            if all_inspections:
                rel_status = derive_release_status(all_inspections)
                if rel_status == "ON_HOLD":
                    reasons.append(f"Quality Hold: Associated production order has quality inspections on HOLD.")
                    category = "POTENTIAL_DELAY" if category == "ON_SCHEDULE" else category
                    risk_level = "HIGH"
                elif rel_status in ("REWORK", "SCRAPPED"):
                    reasons.append(f"Quality Alert: Associated production order reported {rel_status} status during quality inspection.")
                    category = "POTENTIAL_DELAY" if category == "ON_SCHEDULE" else category
                    risk_level = "HIGH"

        return OrderRiskInfo(
            risk_level=risk_level,
            category=category,
            reasons=reasons,
            warnings=warnings,
        )

        return OrderRiskInfo(
            risk_level=risk_level,
            category=category,
            reasons=reasons,
            warnings=warnings,
        )

