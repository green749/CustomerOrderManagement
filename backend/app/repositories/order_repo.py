from typing import Optional, List, Tuple, Dict, Any
from datetime import date
from sqlalchemy import func, desc, asc, select, or_, text
from sqlalchemy.orm import Session, joinedload, selectinload
from ..config import settings
from ..models.business import (
    FactCustomerOrder,
    DimCustomer,
    DimProduct,
    FactShipmentMilestone,
    FactProductionOrder,
    FactQualityInspection,
)


def apply_customer_scope(query, customer_scope: Optional[List[str]], customer_id_col=FactCustomerOrder.customer_id):
    """
    Data segregation helper:
    Filters query by customer_id if customer_scope list is provided and non-empty.
    If customer_scope is None or empty list, returns query unchanged (unrestricted access).
    """
    if customer_scope:
        return query.filter(customer_id_col.in_(customer_scope))
    return query


class OrderRepository:
    @staticmethod
    def list_orders(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        customer_id: Optional[str] = None,
        product_id: Optional[str] = None,
        priority: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        sort_by: str = "order_date",
        sort_order: str = "desc",
        customer_scope: Optional[List[str]] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[FactCustomerOrder], int]:
        query = (
            db.query(FactCustomerOrder)
            .join(DimCustomer, FactCustomerOrder.customer_id == DimCustomer.customer_id)
            .join(DimProduct, FactCustomerOrder.product_id == DimProduct.product_id)
            .options(
                joinedload(FactCustomerOrder.customer),
                joinedload(FactCustomerOrder.product),
                selectinload(FactCustomerOrder.shipments),
            )
        )

        query = apply_customer_scope(query, customer_scope)

        if search and isinstance(search, str):
            clean_search = search.strip().replace("Order #", "").replace("Order ", "").strip()
            s_pat = f"%{clean_search}%"
            s_hyphen = f"%{clean_search.replace(' ', '-')}%"
            query = query.filter(
                or_(
                    FactCustomerOrder.customer_order_id.ilike(s_pat),
                    FactCustomerOrder.customer_order_id.ilike(s_hyphen),
                    DimCustomer.customer_name.ilike(s_pat),
                    DimProduct.product_name.ilike(s_pat),
                )
            )
        if status and isinstance(status, str):
            stat_upper = status.upper().strip()
            if stat_upper in ["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "APPROVAL_PENDING"]:
                from ..models.workflow import CommitmentProposal
                pending_subq = (
                    db.query(CommitmentProposal.customer_order_id)
                    .filter(CommitmentProposal.status == "PENDING")
                    .subquery()
                )
                query = query.filter(
                    or_(
                        FactCustomerOrder.customer_order_id.in_(select(pending_subq.c.customer_order_id)),
                        FactCustomerOrder.order_status.in_(["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING"]),
                        (FactCustomerOrder.order_status == "OPEN") & (FactCustomerOrder.confirmed_delivery_date.is_(None)),
                    )
                )
            elif stat_upper == "IN_PRODUCTION":
                from ..models.workflow import CommitmentProposal
                pending_subq = (
                    db.query(CommitmentProposal.customer_order_id)
                    .filter(CommitmentProposal.status == "PENDING")
                    .subquery()
                )
                query = query.filter(
                    FactCustomerOrder.order_status == "IN_PRODUCTION",
                    FactCustomerOrder.customer_order_id.not_in(select(pending_subq.c.customer_order_id)),
                )
            else:
                query = query.filter(FactCustomerOrder.order_status == stat_upper)
        if customer_id and isinstance(customer_id, str):
            query = query.filter(FactCustomerOrder.customer_id == customer_id)
        if product_id and isinstance(product_id, str):
            query = query.filter(FactCustomerOrder.product_id == product_id)
        if priority and isinstance(priority, str):
            query = query.filter(FactCustomerOrder.priority == priority.upper())
        if start_date:
            query = query.filter(FactCustomerOrder.order_date >= start_date)
        if end_date:
            query = query.filter(FactCustomerOrder.order_date <= end_date)

        # Fast count
        count_q = db.query(func.count(FactCustomerOrder.customer_order_id))
        if search and isinstance(search, str):
            clean_search = search.strip().replace("Order #", "").replace("Order ", "").strip()
            s_pat = f"%{clean_search}%"
            s_hyphen = f"%{clean_search.replace(' ', '-')}%"
            count_q = (
                count_q.join(DimCustomer, FactCustomerOrder.customer_id == DimCustomer.customer_id)
                .join(DimProduct, FactCustomerOrder.product_id == DimProduct.product_id)
                .filter(
                    or_(
                        FactCustomerOrder.customer_order_id.ilike(s_pat),
                        FactCustomerOrder.customer_order_id.ilike(s_hyphen),
                        DimCustomer.customer_name.ilike(s_pat),
                        DimProduct.product_name.ilike(s_pat),
                    )
                )
            )
        count_q = apply_customer_scope(count_q, customer_scope)
        if status and isinstance(status, str):
            stat_upper = status.upper().strip()
            if stat_upper in ["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "APPROVAL_PENDING"]:
                from ..models.workflow import CommitmentProposal
                pending_subq = (
                    db.query(CommitmentProposal.customer_order_id)
                    .filter(CommitmentProposal.status == "PENDING")
                    .subquery()
                )
                count_q = count_q.filter(
                    or_(
                        FactCustomerOrder.customer_order_id.in_(select(pending_subq.c.customer_order_id)),
                        FactCustomerOrder.order_status.in_(["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING"]),
                        (FactCustomerOrder.order_status == "OPEN") & (FactCustomerOrder.confirmed_delivery_date.is_(None)),
                    )
                )
            elif stat_upper == "IN_PRODUCTION":
                from ..models.workflow import CommitmentProposal
                pending_subq = (
                    db.query(CommitmentProposal.customer_order_id)
                    .filter(CommitmentProposal.status == "PENDING")
                    .subquery()
                )
                count_q = count_q.filter(
                    FactCustomerOrder.order_status == "IN_PRODUCTION",
                    FactCustomerOrder.customer_order_id.not_in(select(pending_subq.c.customer_order_id)),
                )
            else:
                count_q = count_q.filter(FactCustomerOrder.order_status == stat_upper)
        if customer_id and isinstance(customer_id, str):
            count_q = count_q.filter(FactCustomerOrder.customer_id == customer_id)
        if product_id and isinstance(product_id, str):
            count_q = count_q.filter(FactCustomerOrder.product_id == product_id)
        if priority and isinstance(priority, str):
            count_q = count_q.filter(FactCustomerOrder.priority == priority.upper())
        if start_date:
            count_q = count_q.filter(FactCustomerOrder.order_date >= start_date)
        if end_date:
            count_q = count_q.filter(FactCustomerOrder.order_date <= end_date)
        total = count_q.scalar() or 0

        # Sorting
        sort_col = getattr(FactCustomerOrder, sort_by, FactCustomerOrder.order_date)
        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_col))
        else:
            query = query.order_by(desc(sort_col))

        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def get_orders_summary(db: Session, customer_scope: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fast aggregated KPI summary over orders using Materialized View when available."""
        if not customer_scope and db.bind.dialect.name == "postgresql":
            try:
                mv_row = db.execute(text("""
                    SELECT 
                        total_orders,
                        delivered_orders,
                        in_production_orders,
                        confirmed_orders,
                        open_orders,
                        overdue_orders
                    FROM mv_order_kpi_summary
                    LIMIT 1;
                """)).mappings().first()
                if mv_row:
                    return {
                        "total_orders": mv_row["total_orders"],
                        "delivered_orders": mv_row["delivered_orders"],
                        "in_production_orders": mv_row["in_production_orders"],
                        "confirmed_orders": mv_row["confirmed_orders"],
                        "open_orders": mv_row["open_orders"],
                        "high_priority_orders": 0,
                        "medium_priority_orders": 0,
                        "low_priority_orders": 0,
                        "overdue_orders": mv_row["overdue_orders"],
                    }
            except Exception:
                pass

        ref_date = settings.effective_reference_date
        sql = text("""
            SELECT 
                count(*) as total_orders,
                count(CASE WHEN order_status = 'DELIVERED' THEN 1 END) as delivered_orders,
                count(CASE WHEN order_status = 'IN_PRODUCTION' THEN 1 END) as in_production_orders,
                count(CASE WHEN order_status = 'CONFIRMED' THEN 1 END) as confirmed_orders,
                count(CASE WHEN order_status = 'OPEN' THEN 1 END) as open_orders,
                count(CASE WHEN priority = 'HIGH' THEN 1 END) as high_priority_orders,
                count(CASE WHEN priority = 'MEDIUM' THEN 1 END) as medium_priority_orders,
                count(CASE WHEN priority = 'LOW' THEN 1 END) as low_priority_orders,
                count(CASE WHEN confirmed_delivery_date < :ref_date AND order_status != 'DELIVERED' THEN 1 END) as overdue_orders
            FROM fact_customer_order
        """)
        row = db.execute(sql, {"ref_date": ref_date}).mappings().first() or {}
        return dict(row)

    @staticmethod
    def infer_production_orders_for_customer_order(
        db: Session,
        customer_order: FactCustomerOrder,
        tolerance_days: int = 7,
    ) -> Tuple[List[FactProductionOrder], str, Optional[str]]:
        """
        Production Linkage Heuristic:
        Finds candidate production orders that match:
          1. Exact customer_order_id match (link_type='DIRECT', confidence='HIGH')
          2. Explicit Heuristic (link_type='INFERRED'):
             - Same product_id
             - due_date within +/- tolerance_days (default 7) of confirmed_delivery_date
             - Cumulative production order_qty >= customer_order.order_qty where possible.
        Confidence:
          - HIGH: direct FK match OR inferred where cumulative qty >= order_qty and due_date within +/-3 days.
          - MEDIUM: inferred where due_date within +/-7 days.
          - LOW: inferred candidate with partial quantity coverage.
        Returns: (matched_production_orders, link_type, confidence)
        """
        # 1. Check direct FK match
        direct_matches = (
            db.query(FactProductionOrder)
            .filter(FactProductionOrder.customer_order_id == customer_order.customer_order_id)
            .options(
                selectinload(FactProductionOrder.inspections),
            )
            .all()
        )
        if direct_matches:
            return direct_matches, "DIRECT", "HIGH"

        # 2. Heuristic candidate lookup
        ref_date = customer_order.confirmed_delivery_date
        from datetime import timedelta
        min_date = ref_date - timedelta(days=tolerance_days)
        max_date = ref_date + timedelta(days=tolerance_days)

        candidates = (
            db.query(FactProductionOrder)
            .filter(
                FactProductionOrder.product_id == customer_order.product_id,
                FactProductionOrder.due_date >= min_date,
                FactProductionOrder.due_date <= max_date,
            )
            .options(
                selectinload(FactProductionOrder.inspections),
            )
            .order_by(
                func.abs(func.julianday(FactProductionOrder.due_date) - func.julianday(ref_date))
                if db.bind.dialect.name == "sqlite"
                else func.abs(FactProductionOrder.due_date - ref_date),
                FactProductionOrder.order_qty.desc(),
            )
            .all()
        )

        if not candidates:
            return [], "UNLINKED", None

        # Select candidates to satisfy cumulative qty >= order_qty where possible
        selected = []
        cum_qty = 0
        for cand in candidates:
            selected.append(cand)
            cum_qty += cand.order_qty
            if cum_qty >= customer_order.order_qty:
                break

        # Confidence rating
        day_diff = min(abs((c.due_date - ref_date).days) for c in selected)
        if cum_qty >= customer_order.order_qty and day_diff <= 3:
            confidence = "HIGH"
        elif day_diff <= 7:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return selected, "INFERRED", confidence

    @staticmethod
    def batch_infer_production_orders(
        db: Session,
        customer_orders: List[FactCustomerOrder],
        tolerance_days: int = 7,
    ) -> Dict[str, Tuple[List[FactProductionOrder], str, Optional[str]]]:
        """
        Batched heuristic linkage for a list/page of customer orders.
        Executes in ONE batched query across all relevant product_ids and due_date bounds,
        preventing N+1 queries.
        """
        if not customer_orders:
            return {}

        product_ids = {o.product_id for o in customer_orders}
        from datetime import timedelta
        min_date = min(o.confirmed_delivery_date for o in customer_orders) - timedelta(days=tolerance_days)
        max_date = max(o.confirmed_delivery_date for o in customer_orders) + timedelta(days=tolerance_days)

        # Batch query production orders
        all_pos = (
            db.query(FactProductionOrder)
            .filter(
                FactProductionOrder.product_id.in_(product_ids),
                FactProductionOrder.due_date >= min_date,
                FactProductionOrder.due_date <= max_date,
            )
            .options(
                selectinload(FactProductionOrder.inspections),
            )
            .all()
        )

        # Index POs by product_id
        po_by_product: Dict[str, List[FactProductionOrder]] = {}
        for po in all_pos:
            po_by_product.setdefault(po.product_id, []).append(po)

        results: Dict[str, Tuple[List[FactProductionOrder], str, Optional[str]]] = {}
        for order in customer_orders:
            # Check direct match
            direct = [p for p in all_pos if p.customer_order_id == order.customer_order_id]
            if direct:
                results[order.customer_order_id] = (direct, "DIRECT", "HIGH")
                continue

            ref_date = order.confirmed_delivery_date
            candidates = [
                p for p in po_by_product.get(order.product_id, [])
                if abs((p.due_date - ref_date).days) <= tolerance_days
            ]
            if not candidates:
                results[order.customer_order_id] = ([], "UNLINKED", None)
                continue

            # Sort by proximity to ref_date, then quantity descending
            candidates.sort(key=lambda p: (abs((p.due_date - ref_date).days), -p.order_qty))
            selected = []
            cum_qty = 0
            for cand in candidates:
                selected.append(cand)
                cum_qty += cand.order_qty
                if cum_qty >= order.order_qty:
                    break

            day_diff = min(abs((c.due_date - ref_date).days) for c in selected)
            if cum_qty >= order.order_qty and day_diff <= 3:
                conf = "HIGH"
            elif day_diff <= 7:
                conf = "MEDIUM"
            else:
                conf = "LOW"

            results[order.customer_order_id] = (selected, "INFERRED", conf)

        return results

    @staticmethod
    def get_order_by_id(
        db: Session,
        customer_order_id: str,
        customer_scope: Optional[List[str]] = None,
    ) -> Optional[FactCustomerOrder]:
        clean_id = customer_order_id.replace("PRE-", "").replace("Order #", "").replace("Order ", "").strip()
        query = (
            db.query(FactCustomerOrder)
            .filter(
                (FactCustomerOrder.customer_order_id == customer_order_id)
                | (FactCustomerOrder.customer_order_id == f"PRE-{clean_id}")
                | (FactCustomerOrder.customer_order_id == clean_id)
                | (FactCustomerOrder.customer_order_id.ilike(f"%{clean_id}%"))
            )
            .options(
                joinedload(FactCustomerOrder.customer),
                joinedload(FactCustomerOrder.product),
                selectinload(FactCustomerOrder.shipments),
            )
        )
        query = apply_customer_scope(query, customer_scope)
        return query.first()

    @staticmethod
    def get_linked_production_orders(db: Session, customer_order_id: str) -> List[FactProductionOrder]:
        """Fetch production orders linked to this customer order."""
        return (
            db.query(FactProductionOrder)
            .filter(FactProductionOrder.customer_order_id == customer_order_id)
            .options(
                selectinload(FactProductionOrder.inspections),
            )
            .all()
        )

