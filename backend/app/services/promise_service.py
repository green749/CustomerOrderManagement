import math
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload, joinedload

from ..config import settings
from ..models.business import (
    FactCustomerOrder,
    FactProductionOrder,
    FactInventoryDailySnapshot,
    FactShipmentMilestone,
    DimProduct,
    DimCustomer,
)
from ..repositories.order_repo import OrderRepository
from ..schemas.promise import (
    MaterialATPItem,
    ATPCheckResult,
    CTPCheckResult,
    PromiseRecommendationResult,
    AllocationItem,
    AllocationProposalResponse,
)


def to_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return datetime.fromisoformat(str(val)).date()
    except Exception:
        return None


# Reference BOM components mapped directly from data/data/fact_bom_component.csv
PRODUCT_BOM_MAP: Dict[str, List[Dict[str, Any]]] = {
    "SPH-A15-128": [
        {"material_id": "MAT-SOC-001", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-MEM-002", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-NAND-003", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-PCB-004", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-DSP-005", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-BAT-006", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-CAM-007", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-CAM-008", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-HSG-009", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-GLS-010", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-SPK-011", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-ANT-012", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-CON-013", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-BOX-014", "component_qty": 1, "scrap_factor": 0.001},
        {"material_id": "MAT-CBL-015", "component_qty": 1, "scrap_factor": 0.001},
        {"material_id": "MAT-SCR-016", "component_qty": 1, "scrap_factor": 0.005},
    ],
    "SPH-A15-256": [
        {"material_id": "MAT-SOC-001", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-MEM-002", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-NAND-003", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-PCB-004", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-DSP-005", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-BAT-006", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-CAM-007", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-CAM-008", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-HSG-009", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-GLS-010", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-SPK-011", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-ANT-012", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-CON-013", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-BOX-014", "component_qty": 1, "scrap_factor": 0.001},
        {"material_id": "MAT-CBL-015", "component_qty": 1, "scrap_factor": 0.001},
        {"material_id": "MAT-SCR-016", "component_qty": 1, "scrap_factor": 0.005},
    ],
    "SPH-PRO-256": [
        {"material_id": "MAT-SOC-001", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-MEM-002", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-NAND-003", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-PCB-004", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-DSP-005", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-BAT-006", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-CAM-007", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-CAM-008", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-HSG-009", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-GLS-010", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-SPK-011", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-ANT-012", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-CON-013", "component_qty": 1, "scrap_factor": 0.005},
        {"material_id": "MAT-BOX-014", "component_qty": 1, "scrap_factor": 0.001},
        {"material_id": "MAT-CBL-015", "component_qty": 1, "scrap_factor": 0.001},
        {"material_id": "MAT-SCR-016", "component_qty": 1, "scrap_factor": 0.005},
    ],
}

MATERIAL_LEAD_TIMES: Dict[str, int] = {
    "MAT-SOC-001": 12, "MAT-MEM-002": 8, "MAT-NAND-003": 23, "MAT-PCB-004": 5,
    "MAT-DSP-005": 12, "MAT-BAT-006": 5, "MAT-CAM-007": 25, "MAT-CAM-008": 12,
    "MAT-HSG-009": 13, "MAT-GLS-010": 27, "MAT-SPK-011": 13, "MAT-ANT-012": 35,
    "MAT-CON-013": 7, "MAT-BOX-014": 16, "MAT-CBL-015": 13, "MAT-SCR-016": 19,
    "MAT-PASTE-017": 34, "MAT-ADH-018": 22,
}

CARRIER_TRANSIT_BUFFER: Dict[str, int] = {
    "BlueDart": 4,
    "DHL": 4,
    "Delhivery": 4,
    "Safexpress": 5,
}


class PromiseService:
    """
    Plain rule-based Python service for ATP, CTP, promise date recommendations,
    and greedy constrained inventory allocation.
    """

    @staticmethod
    def check_atp(
        db: Session,
        customer_order_id: str,
        order: Optional[FactCustomerOrder] = None,
    ) -> ATPCheckResult:
        """
        Check Available-to-Promise (ATP) for the order's product:
        - Uses fact_bom_component: required = component_qty x (1 + scrap_factor) x order_qty
        - Uses latest fact_inventory_daily_snapshot:
            usable = on_hand - allocated - blocked - quality_hold (floor 0)
            in_transit is reported separately, not counted as available
        - Returns per-material breakdown, shortfall, and limiting material.
        - Also returns finished goods availability in FG-WH-01.
        """
        if order is None:
            order = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == customer_order_id).first()
        if not order:
            raise ValueError(f"Customer order '{customer_order_id}' not found.")

        product_id = order.product_id
        from ..models.operational import FactBOMComponent, DimMaterial
        db_boms = db.query(FactBOMComponent).filter(FactBOMComponent.product_id == product_id).all()
        if db_boms:
            bom_items = [
                {
                    "material_id": b.material_id,
                    "component_qty": float(b.component_qty),
                    "scrap_factor": float(b.scrap_factor or 0.005),
                }
                for b in db_boms
            ]
            has_db_bom = True
        else:
            bom_items = PRODUCT_BOM_MAP.get(product_id, [])
            has_db_bom = False

        bom_mat_ids = [b["material_id"] for b in bom_items]

        # Fetch actual lead times from DimMaterial
        db_mats = {
            m.material_id: m.lead_time_days
            for m in db.query(DimMaterial).filter(DimMaterial.material_id.in_(bom_mat_ids)).all()
        }

        # Latest snapshot date
        latest_date = (
            db.query(func.max(FactInventoryDailySnapshot.snapshot_date)).scalar()
            or settings.effective_reference_date
        )

        # Query only BOM component materials and FG warehouse rows (avoids fetching 6,600+ rows over WAN)
        snapshots = (
            db.query(FactInventoryDailySnapshot)
            .filter(
                FactInventoryDailySnapshot.snapshot_date == latest_date,
                (FactInventoryDailySnapshot.material_id.in_(bom_mat_ids))
                | (FactInventoryDailySnapshot.warehouse_id == "FG-WH-01"),
            )
            .all()
        )

        # Aggregate raw material usable & in-transit inventory across non-FG warehouses
        rm_usable: Dict[str, float] = {}
        rm_in_transit: Dict[str, float] = {}
        fg_on_hand = 0
        fg_usable = 0

        for s in snapshots:
            usable = max(0, s.on_hand_qty - s.allocated_qty - s.blocked_qty - s.quality_hold_qty)
            if s.warehouse_id == "FG-WH-01":
                fg_on_hand += s.on_hand_qty
                fg_usable += usable
            else:
                rm_usable[s.material_id] = rm_usable.get(s.material_id, 0.0) + float(usable)
                rm_in_transit[s.material_id] = rm_in_transit.get(s.material_id, 0.0) + float(s.in_transit_qty)

        material_items: List[MaterialATPItem] = []
        is_feasible = True
        limiting_mat: Optional[str] = None
        min_producible = float("inf")

        for b in bom_items:
            m_id = b["material_id"]
            comp_qty = b["component_qty"]
            scrap = b["scrap_factor"]
            required = float(comp_qty) * (1.0 + float(scrap)) * float(order.order_qty)
            usable = rm_usable.get(m_id, 0.0)
            shortfall = max(0.0, required - usable)
            in_transit = rm_in_transit.get(m_id, 0.0)
            lead_time = db_mats.get(m_id) if db_mats.get(m_id) is not None else MATERIAL_LEAD_TIMES.get(m_id, 14)

            # Producible units based on this component
            unit_req = float(comp_qty) * (1.0 + float(scrap))
            producible_for_mat = math.floor(usable / unit_req) if unit_req > 0 else 0
            if producible_for_mat < min_producible:
                min_producible = producible_for_mat
                limiting_mat = m_id

            if shortfall > 0:
                is_feasible = False

            material_items.append(
                MaterialATPItem(
                    material_id=m_id,
                    component_qty_per_unit=comp_qty,
                    scrap_factor=scrap,
                    required_qty=round(required, 2),
                    usable_qty=round(usable, 2),
                    shortfall_qty=round(shortfall, 2),
                    in_transit_qty=round(in_transit, 2),
                    lead_time_days=lead_time,
                )
            )

        # Flag the limiting item
        for m in material_items:
            if m.material_id == limiting_mat:
                m.is_limiting = True

        return ATPCheckResult(
            customer_order_id=order.customer_order_id,
            product_id=product_id,
            order_qty=order.order_qty,
            as_of_date=latest_date,
            is_atp_feasible=is_feasible,
            limiting_material_id=limiting_mat,
            max_producible_units=int(min_producible if min_producible != float("inf") else 0),
            finished_goods_inventory={
                "warehouse_id": "FG-WH-01",
                "on_hand_qty": fg_on_hand,
                "usable_qty": fg_usable,
                "note": "Raw material inventory stored in FG-WH-01. Product-level finished goods stock is not tracked in source records.",
            },
            materials=material_items,
            status="VERIFIED" if has_db_bom else "INSUFFICIENT_DATA",
            data_gap_warning=(
                None if has_db_bom else (
                    "No verified Bill of Materials (BOM) table exists in the connected database. "
                    "Material availability calculations are unverified estimates and cannot be presented as verified availability."
                )
            ),
        )

    @staticmethod
    def check_ctp(
        db: Session,
        customer_order_id: str,
        order: Optional[FactCustomerOrder] = None,
        po_list: Optional[List[FactProductionOrder]] = None,
        link_type: Optional[str] = None,
        link_conf: Optional[str] = None,
    ) -> CTPCheckResult:
        """
        Check Capable-to-Promise (CTP):
        - Remaining qty = order_qty - shipped_qty
        - Compares with linked production orders (qty, planned_finish, status)
        - Uses dim_product.standard_cycle_sec and 3 shifts x 7 hours (1260 mins/day)
        - Computes producible_by date and explicit assumptions.
        """
        if order is None:
            order = (
                db.query(FactCustomerOrder)
                .options(joinedload(FactCustomerOrder.product))
                .filter(FactCustomerOrder.customer_order_id == customer_order_id)
                .first()
            )
        if not order:
            raise ValueError(f"Customer order '{customer_order_id}' not found.")

        remaining_qty = max(0, order.order_qty - order.shipped_qty)

        # Product cycle time
        product = getattr(order, "product", None)
        if not product:
            product = db.query(DimProduct).filter(DimProduct.product_id == order.product_id).first()
        cycle_sec = product.standard_cycle_sec if product and product.standard_cycle_sec else 45

        # Capacity: 1260 working minutes per day = 75,600 seconds per line per day
        working_sec_per_day = 1260 * 60
        daily_capacity_units = math.floor(working_sec_per_day / cycle_sec)

        # Production order linkage
        if po_list is None or link_type is None:
            po_list, link_type, link_conf = OrderRepository.infer_production_orders_for_customer_order(db, order)

        # Check existing planned finish dates
        max_po_finish = None
        for po in po_list:
            finish_d = to_date(po.planned_finish)
            if finish_d:
                max_po_finish = max(max_po_finish or finish_d, finish_d)

        # Compute production duration
        days_to_produce = math.ceil(remaining_qty / daily_capacity_units) if remaining_qty > 0 else 0

        current_date = settings.effective_reference_date
        assumptions = [
            f"Nominal capacity based on standard cycle time: {cycle_sec}s/unit",
            f"Daily plant capacity: {daily_capacity_units} units/day (3 shifts x 7.0 net working hours)",
            f"Production linkage: {link_type} ({link_conf or 'N/A'}) with {len(po_list)} order(s)",
        ]

        if max_po_finish and max_po_finish >= current_date:
            producible_by = max_po_finish
            assumptions.append(f"Producible by existing scheduled production finish: {producible_by}")
        else:
            producible_by = current_date + timedelta(days=days_to_produce)
            assumptions.append(f"Producible by new production sequence starting from reference date ({current_date})")

        po_dicts = [
            {
                "production_order_id": po.production_order_id,
                "plant_id": po.plant_id,
                "order_qty": po.order_qty,
                "planned_finish": str(po.planned_finish),
                "order_status": po.order_status,
                "due_date": str(po.due_date),
            }
            for po in po_list
        ]

        ctp_status = "VERIFIED" if link_type == "DIRECT" else "INSUFFICIENT_DATA"
        ctp_warning = (
            None if link_type == "DIRECT"
            else "No verified direct production order linkage exists in manufacturing execution records (production order IDs do not match customer order IDs). Producible date is an unverified capacity proxy, not a verified production schedule."
        )
        if ctp_warning:
            assumptions.insert(0, f"DATA_STATUS: {ctp_status} - {ctp_warning}")

        return CTPCheckResult(
            customer_order_id=order.customer_order_id,
            product_id=order.product_id,
            order_qty=order.order_qty,
            shipped_qty=order.shipped_qty,
            remaining_qty=remaining_qty,
            standard_cycle_sec=cycle_sec,
            daily_capacity_units=daily_capacity_units,
            days_to_produce=days_to_produce,
            producible_by=producible_by,
            linked_production_orders=po_dicts,
            assumptions=assumptions,
            status=ctp_status,
            data_gap_warning=ctp_warning,
        )

    @staticmethod
    def recommend_promise_date(
        db: Session,
        customer_order_id: str,
        order: Optional[FactCustomerOrder] = None,
    ) -> PromiseRecommendationResult:
        """
        Generate feasible promise-date recommendation:
        Earliest feasible date = max(
            ATP material ready date (using dim_material.lead_time_days for shortfalls),
            CTP producible_by,
            + transit buffer from customer's preferred carrier history
        )
        Returns conflicts: MATERIAL_SHORTAGE, QUALITY_HOLD, CAPACITY, OVERDUE, DATA_GAP
        """
        if order is None:
            order = (
                db.query(FactCustomerOrder)
                .options(joinedload(FactCustomerOrder.customer), joinedload(FactCustomerOrder.product))
                .filter(FactCustomerOrder.customer_order_id == customer_order_id)
                .first()
            )
        if not order:
            raise ValueError(f"Customer order '{customer_order_id}' not found.")

        # Infer production orders once and reuse across CTP and quality checks
        po_list, link_type, link_conf = OrderRepository.infer_production_orders_for_customer_order(db, order)

        atp = PromiseService.check_atp(db, customer_order_id, order=order)
        ctp = PromiseService.check_ctp(db, customer_order_id, order=order, po_list=po_list, link_type=link_type, link_conf=link_conf)

        customer = getattr(order, "customer", None)
        if not customer:
            customer = db.query(DimCustomer).filter(DimCustomer.customer_id == order.customer_id).first()
        carrier = customer.preferred_carrier if customer and customer.preferred_carrier else "Delhivery"
        transit_buffer = CARRIER_TRANSIT_BUFFER.get(carrier, 4)

        conflicts = []
        explanations = []

        current_date = settings.effective_reference_date

        # 1. ATP readiness date
        max_lead_time_shortfall = 0
        for m in atp.materials:
            if m.shortfall_qty > 0:
                conflicts.append("MATERIAL_SHORTAGE")
                max_lead_time_shortfall = max(max_lead_time_shortfall, m.lead_time_days)
                explanations.append(f"Material {m.material_id} shortfall of {m.shortfall_qty} units (requires {m.lead_time_days} days lead time)")

        atp_ready_date = current_date + timedelta(days=max_lead_time_shortfall)

        # 2. CTP readiness date
        ctp_date = ctp.producible_by

        # 3. Quality conflicts (reusing po_list, no duplicate DB queries)
        all_inspections = []
        for po in po_list:
            if po.inspections:
                all_inspections.extend(po.inspections)
        has_hold = any(getattr(i, "disposition", "").upper() == "HOLD" for i in all_inspections)
        if has_hold:
            conflicts.append("QUALITY_HOLD")
            explanations.append("Associated production order contains inspections currently on HOLD")

        # 4. Overdue conflict
        confirmed_date = to_date(order.confirmed_delivery_date)
        requested_date = to_date(order.requested_delivery_date)
        if confirmed_date and confirmed_date < current_date and order.order_status != "DELIVERED":
            conflicts.append("OVERDUE")
            explanations.append(f"Original confirmed delivery date ({confirmed_date}) is in the past")

        # 5. Data Gap conflict
        conflicts.append("DATA_GAP")
        if link_type == "UNLINKED":
            explanations.append("No production order could be linked directly or heuristically")
        else:
            explanations.append("BOM data and production order linkage are unverified in source database; date is an uncommitted recommendation")

        # Base manufacture ready date = max(atp_ready_date, ctp_date)
        ready_for_dispatch = max(atp_ready_date, ctp_date)
        recommended_date = ready_for_dispatch + timedelta(days=transit_buffer)
        delta_days = (recommended_date - confirmed_date).days if confirmed_date else 0

        # Deduplicate conflicts
        unique_conflicts = list(dict.fromkeys(conflicts))

        # Confidence rating
        confidence = "LOW"  # Low confidence due to unverified BOM and production linkage

        return PromiseRecommendationResult(
            customer_order_id=order.customer_order_id,
            product_id=order.product_id,
            customer_id=order.customer_id,
            carrier=carrier,
            requested_delivery_date=order.requested_delivery_date,
            confirmed_delivery_date=order.confirmed_delivery_date,
            recommended_date=recommended_date,
            delta_days_vs_confirmed=delta_days,
            confidence=confidence,
            conflicts=unique_conflicts,
            transit_buffer_days=transit_buffer,
            atp_ready_date=atp_ready_date,
            ctp_producible_by=ctp_date,
            explanations=explanations,
            status="ESTIMATED_RECOMMENDATION",
            data_gap_warning=(
                "Recommendation relies on unverified BOM estimates and inferred production capacity. "
                "Must be reviewed by an authorized manager before commercial confirmation."
            ),
        )

    @staticmethod
    def propose_allocation(db: Session, product_id: Optional[str] = None) -> AllocationProposalResponse:
        """
        Greedy constrained stock allocation for competing open orders:
        - Priority ranking: HIGH (3) > MEDIUM (2) > LOW (1)
        - Customer service level: OTIF-95 > Standard
        - Earliest requested delivery date
        Allocates available stock greedily; returns proposed_qty and unfulfilled_qty per order.
        """
        # Query open or confirmed orders
        query = (
            db.query(FactCustomerOrder)
            .join(DimCustomer, FactCustomerOrder.customer_id == DimCustomer.customer_id)
            .options(joinedload(FactCustomerOrder.customer))
            .filter(FactCustomerOrder.order_status.in_(("OPEN", "CONFIRMED")))
        )
        if product_id:
            query = query.filter(FactCustomerOrder.product_id == product_id)

        orders = query.all()

        # Determine total usable finished goods or producible units
        latest_date = (
            db.query(func.max(FactInventoryDailySnapshot.snapshot_date)).scalar()
            or settings.effective_reference_date
        )
        fg_snapshots = (
            db.query(FactInventoryDailySnapshot)
            .filter(
                FactInventoryDailySnapshot.snapshot_date == latest_date,
                FactInventoryDailySnapshot.warehouse_id == "FG-WH-01",
            )
            .all()
        )
        # Net usable inventory in FG
        total_usable_fg = sum(
            max(0, s.on_hand_qty - s.allocated_qty - s.blocked_qty - s.quality_hold_qty)
            for s in fg_snapshots
        )

        # Ranking tuples: priority_weight, service_level_weight, earliest requested_delivery_date
        priority_weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        service_weights = {"OTIF-95": 2, "STANDARD": 1}

        def sort_key(o: FactCustomerOrder):
            p_w = priority_weights.get(o.priority.upper(), 1) if o.priority else 1
            s_level = o.customer.service_level.upper() if o.customer and o.customer.service_level else "STANDARD"
            s_w = service_weights.get(s_level, 1)
            req_date = o.requested_delivery_date or date(2099, 1, 1)
            # Higher priority & service level first, earlier date first
            return (-p_w, -s_w, req_date)

        sorted_orders = sorted(orders, key=sort_key)

        remaining_stock = total_usable_fg
        total_demanded = sum(o.order_qty for o in sorted_orders)
        total_allocated = 0
        total_unfulfilled = 0

        allocation_items: List[AllocationItem] = []

        for o in sorted_orders:
            demanded = o.order_qty
            allocated = min(remaining_stock, demanded)
            unfulfilled = demanded - allocated
            remaining_stock -= allocated
            total_allocated += allocated
            total_unfulfilled += unfulfilled

            if allocated == demanded:
                status_str = "FULL"
            elif allocated > 0:
                status_str = "PARTIAL"
            else:
                status_str = "UNFULFILLED"

            allocation_items.append(
                AllocationItem(
                    customer_order_id=o.customer_order_id,
                    customer_id=o.customer_id,
                    customer_name=o.customer.customer_name if o.customer else o.customer_id,
                    service_level=o.customer.service_level if o.customer else "STANDARD",
                    priority=o.priority,
                    requested_delivery_date=o.requested_delivery_date,
                    order_qty=demanded,
                    allocated_qty=allocated,
                    unfulfilled_qty=unfulfilled,
                    allocation_status=status_str,
                )
            )

        return AllocationProposalResponse(
            product_id=product_id,
            total_usable_inventory_units=total_usable_fg,
            total_demanded_units=total_demanded,
            total_allocated_units=total_allocated,
            total_unfulfilled_units=total_unfulfilled,
            allocations=allocation_items,
            status="UNSUPPORTED_DATA",
            data_gap_warning=(
                "Inventory snapshot records track raw material IDs (MAT-*), not finished product SKUs (SPH-*). "
                "Finished goods allocation across customer orders is unsupported by source data."
            ),
        )


def check_atp(db: Session, customer_order_id: str, order: Optional[FactCustomerOrder] = None) -> ATPCheckResult:
    """Module-level function: check ATP using BOM and latest inventory snapshot."""
    return PromiseService.check_atp(db, customer_order_id, order=order)


def check_ctp(db: Session, customer_order_id: str, order: Optional[FactCustomerOrder] = None) -> CTPCheckResult:
    """Module-level function: check CTP using remaining qty, cycle time, and production plan."""
    return PromiseService.check_ctp(db, customer_order_id, order=order)


def recommend_promise_date(db: Session, customer_order_id: str, order: Optional[FactCustomerOrder] = None) -> PromiseRecommendationResult:
    """Module-level function: generate feasible promise-date recommendation with conflicts."""
    return PromiseService.recommend_promise_date(db, customer_order_id, order=order)


def propose_allocation(db: Session, product_id: Optional[str] = None) -> AllocationProposalResponse:
    """Module-level function: greedy constrained allocation proposal."""
    return PromiseService.propose_allocation(db, product_id)

