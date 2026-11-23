from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload, selectinload
from ..repositories.dashboard_repo import DashboardRepository
from ..repositories.order_repo import OrderRepository
from ..models.business import FactCustomerOrder, DimCustomer, DimProduct, FactShipmentMilestone
from ..schemas.dashboard import (
    DashboardSummary,
    OrderStatusCount,
    AtRiskOrderItem,
    AtRiskSummaryResponse,
)
from ..schemas.order import OrderRiskInfo
from .risk_service import OrderRiskAnalyzer, derive_release_status
from .cache_service import get_cached, set_cached
from ..config import settings


class DashboardService:
    @staticmethod
    def get_summary(db: Session, as_of_date: Optional[date] = None) -> DashboardSummary:
        cache_key = f"dashboard_summary_{as_of_date}"
        cached = get_cached(cache_key)
        if cached:
            return DashboardSummary(**cached) if isinstance(cached, dict) else cached
        data = DashboardRepository.get_summary(db, as_of_date=as_of_date)
        res = DashboardSummary(**data)
        set_cached(cache_key, res.model_dump(), ttl_seconds=60)
        return res

    @staticmethod
    def get_order_status_distribution(db: Session) -> List[OrderStatusCount]:
        cache_key = "dashboard_order_status_distribution"
        cached = get_cached(cache_key)
        if cached:
            return [OrderStatusCount(**item) if isinstance(item, dict) else item for item in cached]
        data = DashboardRepository.get_order_status_distribution(db)
        res = [OrderStatusCount(**item) for item in data]
        set_cached(cache_key, [item.model_dump() for item in res], ttl_seconds=60)
        return res

    @staticmethod
    def get_at_risk_orders(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        risk_category: Optional[str] = None,  # ACTUAL_DELAY, POTENTIAL_DELAY, UNKNOWN_RISK
        as_of_date: Optional[date] = None,
    ) -> AtRiskSummaryResponse:
        """
        Computes at-risk orders with database-level filtering and batched pagination.
        Does NOT load all 1,500 orders into Python memory.
        """
        cache_key = f"at_risk_{page}_{page_size}_{risk_category}_{as_of_date}"
        cached = get_cached(cache_key)
        if cached:
            return AtRiskSummaryResponse(**cached) if isinstance(cached, dict) else cached

        effective_date = as_of_date or settings.effective_reference_date
        horizon_date = effective_date + timedelta(days=3)
        cat_upper = risk_category.upper() if risk_category else None

        from sqlalchemy import text
        counts_sql = text("""
        WITH delayed_milestones AS (
            SELECT DISTINCT customer_order_id FROM fact_shipment_milestone WHERE shipment_status = 'DELAYED'
        ),
        actual_delayed AS (
            SELECT customer_order_id FROM fact_customer_order WHERE order_status != 'DELIVERED' AND confirmed_delivery_date < :eff_date
            UNION
            SELECT customer_order_id FROM delayed_milestones
        ),
        potential_delayed AS (
            SELECT customer_order_id FROM fact_customer_order
            WHERE order_status IN ('OPEN', 'CONFIRMED')
              AND confirmed_delivery_date >= :eff_date
              AND confirmed_delivery_date <= :horizon_date
              AND customer_order_id NOT IN (SELECT customer_order_id FROM actual_delayed)
        ),
        active_products AS (
            SELECT DISTINCT product_id FROM fact_production_order
        ),
        unknown_risk AS (
            SELECT customer_order_id FROM fact_customer_order
            WHERE order_status IN ('OPEN', 'CONFIRMED', 'IN_PRODUCTION')
              AND product_id NOT IN (SELECT product_id FROM active_products)
              AND customer_order_id NOT IN (SELECT customer_order_id FROM actual_delayed)
              AND customer_order_id NOT IN (SELECT customer_order_id FROM potential_delayed)
        )
        SELECT 
            (SELECT COUNT(*) FROM actual_delayed) as actual_count,
            (SELECT COUNT(*) FROM potential_delayed) as potential_count,
            (SELECT COUNT(*) FROM unknown_risk) as unknown_count
        """)
        c_row = db.execute(counts_sql, {
            "eff_date": str(effective_date),
            "horizon_date": str(horizon_date),
        }).mappings().first()

        actual_count = c_row["actual_count"] or 0
        potential_count = c_row["potential_count"] or 0
        unknown_count = c_row["unknown_count"] or 0
        total_at_risk = actual_count + potential_count + unknown_count

        # Target filter
        if cat_upper == "ACTUAL_DELAY":
            target_filter = "SELECT customer_order_id FROM actual_delayed"
        elif cat_upper == "POTENTIAL_DELAY":
            target_filter = "SELECT customer_order_id FROM potential_delayed"
        elif cat_upper == "UNKNOWN_RISK":
            target_filter = "SELECT customer_order_id FROM unknown_risk"
        else:
            target_filter = "SELECT customer_order_id FROM actual_delayed UNION SELECT customer_order_id FROM potential_delayed UNION SELECT customer_order_id FROM unknown_risk"

        slice_sql = text(f"""
        WITH delayed_milestones AS (
            SELECT DISTINCT customer_order_id FROM fact_shipment_milestone WHERE shipment_status = 'DELAYED'
        ),
        actual_delayed AS (
            SELECT customer_order_id FROM fact_customer_order WHERE order_status != 'DELIVERED' AND confirmed_delivery_date < :eff_date
            UNION
            SELECT customer_order_id FROM delayed_milestones
        ),
        potential_delayed AS (
            SELECT customer_order_id FROM fact_customer_order
            WHERE order_status IN ('OPEN', 'CONFIRMED')
              AND confirmed_delivery_date >= :eff_date
              AND confirmed_delivery_date <= :horizon_date
              AND customer_order_id NOT IN (SELECT customer_order_id FROM actual_delayed)
        ),
        active_products AS (
            SELECT DISTINCT product_id FROM fact_production_order
        ),
        unknown_risk AS (
            SELECT customer_order_id FROM fact_customer_order
            WHERE order_status IN ('OPEN', 'CONFIRMED', 'IN_PRODUCTION')
              AND product_id NOT IN (SELECT product_id FROM active_products)
              AND customer_order_id NOT IN (SELECT customer_order_id FROM actual_delayed)
              AND customer_order_id NOT IN (SELECT customer_order_id FROM potential_delayed)
        ),
        target_orders AS (
            {target_filter}
        )
        SELECT o.customer_order_id
        FROM fact_customer_order o
        JOIN target_orders t ON o.customer_order_id = t.customer_order_id
        ORDER BY 
            CASE o.priority 
                WHEN 'URGENT' THEN 4 
                WHEN 'HIGH' THEN 3 
                WHEN 'MEDIUM' THEN 2 
                WHEN 'LOW' THEN 1 
                ELSE 0 
            END DESC,
            o.confirmed_delivery_date ASC
        LIMIT :limit OFFSET :offset
        """)

        slice_rows = db.execute(slice_sql, {
            "eff_date": str(effective_date),
            "horizon_date": str(horizon_date),
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }).fetchall()
        page_target_ids = [r[0] for r in slice_rows]

        if not page_target_ids:
            return AtRiskSummaryResponse(
                total_at_risk=total_at_risk,
                actual_delayed=actual_count,
                potential_delayed=potential_count,
                unknown_risk=unknown_count,
                items=[],
            )

        # 6. Fetch full ORM entities for ONLY the current page slice
        paged_orders = (
            db.query(FactCustomerOrder)
            .filter(FactCustomerOrder.customer_order_id.in_(page_target_ids))
            .options(
                joinedload(FactCustomerOrder.customer),
                joinedload(FactCustomerOrder.product),
                selectinload(FactCustomerOrder.shipments),
            )
            .all()
        )
        # Preserve sort order of page_target_ids
        order_map = {o.customer_order_id: o for o in paged_orders}
        sorted_orders = [order_map[oid] for oid in page_target_ids if oid in order_map]

        # 7. Batched production order heuristic linkage for ONLY the paginated slice
        linked_pos_map = OrderRepository.batch_infer_production_orders(db, sorted_orders)

        items: List[AtRiskOrderItem] = []
        for o in sorted_orders:
            linked_pos, link_type, link_conf = linked_pos_map.get(
                o.customer_order_id, ([], "UNLINKED", None)
            )
            all_inspections = []
            for p in linked_pos:
                if p.inspections:
                    all_inspections.extend(p.inspections)
            rel_status = derive_release_status(all_inspections)

            risk = OrderRiskAnalyzer.evaluate_order(
                order=o,
                shipments=o.shipments,
                production_orders=linked_pos,
                as_of_date=effective_date,
                link_type=link_type,
                link_confidence=link_conf,
            )

            item = AtRiskOrderItem(
                customer_order_id=o.customer_order_id,
                customer_name=o.customer.customer_name if o.customer else o.customer_id,
                product_name=o.product.product_name if o.product else o.product_id,
                order_status=o.order_status,
                priority=o.priority,
                confirmed_delivery_date=str(o.confirmed_delivery_date),
                order_qty=o.order_qty,
                shipped_qty=o.shipped_qty,
                risk=risk,
                link_type=link_type,
                link_confidence=link_conf,
                release_status=rel_status,
            )
            items.append(item)

        res = AtRiskSummaryResponse(
            total_at_risk=total_at_risk,
            actual_delayed=actual_count,
            potential_delayed=potential_count,
            unknown_risk=unknown_count,
            items=items,
        )
        set_cached(cache_key, res.model_dump(), ttl_seconds=60)
        return res

    @staticmethod
    def get_analytics(db: Session) -> Dict[str, Any]:
        """
        Calculates authoritative real database aggregations for comprehensive overview charts:
        - Manufacturing plant throughput & adherence (dim_plant, fact_production_order)
        - Product demand & revenue distribution (dim_product, fact_customer_order)
        - Carrier delivery reliability & utilization (fact_shipment_milestone)
        - Quality yield, holds & scrap rates (fact_quality_inspection)
        - Department operational risk distribution (risk_alerts)
        - Customer fulfillment by tier (dim_customer, fact_customer_order)
        - Promise date buffer splits & backlog ageing
        """
        cache_key = "dashboard_analytics_v1"
        cached = get_cached(cache_key)
        if cached:
            return cached

        from sqlalchemy import text
        from .kpi_service import KPIService

        # 1. Plant Performance
        plants_res = db.execute(text("""
            SELECT 
                p.plant_id, 
                p.plant_name, 
                COUNT(po.production_order_id) as total_pos,
                SUM(CASE WHEN po.order_status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN po.order_status = 'IN_PRODUCTION' THEN 1 ELSE 0 END) as in_progress,
                COALESCE(SUM(po.order_qty), 0) as total_units,
                ROUND(CAST(AVG(CASE WHEN po.planned_finish <= po.due_date THEN 100.0 ELSE 0.0 END) AS numeric), 1) as adherence_pct
            FROM dim_plant p
            LEFT JOIN fact_production_order po ON p.plant_id = po.plant_id
            GROUP BY p.plant_id, p.plant_name
            ORDER BY total_pos DESC;
        """)).mappings().all()
        plants = [
            {
                "plant_id": r["plant_id"],
                "plant_name": r["plant_name"],
                "total_pos": int(r["total_pos"] or 0),
                "completed": int(r["completed"] or 0),
                "in_progress": int(r["in_progress"] or 0),
                "total_units": int(r["total_units"] or 0),
                "adherence_pct": float(r["adherence_pct"] or 0.0),
            }
            for r in plants_res
        ]

        # 2. Product Demand
        prod_res = db.execute(text("""
            SELECT 
                dp.product_id,
                dp.product_name,
                COUNT(fo.customer_order_id) as total_orders,
                COALESCE(SUM(fo.order_qty), 0) as total_demand_units,
                COALESCE(SUM(fo.order_qty * fo.unit_price_inr), 0) as total_revenue_inr
            FROM dim_product dp
            LEFT JOIN fact_customer_order fo ON dp.product_id = fo.product_id
            GROUP BY dp.product_id, dp.product_name
            ORDER BY total_demand_units DESC;
        """)).mappings().all()
        products = [
            {
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "total_orders": int(r["total_orders"] or 0),
                "total_demand_units": int(r["total_demand_units"] or 0),
                "total_revenue_inr": float(r["total_revenue_inr"] or 0),
            }
            for r in prod_res
        ]

        # 3. Carrier Performance
        carrier_res = db.execute(text("""
            SELECT 
                carrier,
                COUNT(shipment_id) as total_shipments,
                SUM(CASE WHEN shipment_status != 'DELAYED' THEN 1 ELSE 0 END) as on_time_shipments,
                SUM(CASE WHEN shipment_status = 'DELAYED' THEN 1 ELSE 0 END) as delayed_shipments,
                ROUND(CAST(AVG(CASE WHEN shipment_status != 'DELAYED' THEN 100.0 ELSE 0.0 END) AS numeric), 1) as on_time_pct,
                ROUND(CAST(AVG(vehicle_utilization_pct) AS numeric), 1) as avg_utilization_pct
            FROM fact_shipment_milestone
            WHERE carrier IS NOT NULL AND carrier != ''
            GROUP BY carrier
            ORDER BY total_shipments DESC;
        """)).mappings().all()
        carriers = [
            {
                "carrier": r["carrier"],
                "total_shipments": int(r["total_shipments"] or 0),
                "on_time_shipments": int(r["on_time_shipments"] or 0),
                "delayed_shipments": int(r["delayed_shipments"] or 0),
                "on_time_pct": float(r["on_time_pct"] or 0.0),
                "avg_utilization_pct": float(r["avg_utilization_pct"] or 0.0),
            }
            for r in carrier_res
        ]

        # 4. Quality Yield
        q_res = db.execute(text("""
            SELECT 
                COUNT(inspection_id) as total_inspections,
                SUM(CASE WHEN disposition = 'RELEASE' THEN 1 ELSE 0 END) as release_count,
                SUM(CASE WHEN disposition = 'HOLD' THEN 1 ELSE 0 END) as hold_count,
                SUM(CASE WHEN disposition = 'SCRAP' THEN 1 ELSE 0 END) as scrap_count,
                ROUND(CAST(AVG(CASE WHEN disposition = 'RELEASE' THEN 100.0 ELSE 0.0 END) AS numeric), 1) as yield_pct
            FROM fact_quality_inspection;
        """)).mappings().first()
        quality = {
            "total_inspections": int(q_res["total_inspections"] or 0),
            "release_count": int(q_res["release_count"] or 0),
            "hold_count": int(q_res["hold_count"] or 0),
            "scrap_count": int(q_res["scrap_count"] or 0),
            "yield_pct": float(q_res["yield_pct"] or 0.0),
        }

        # 5. Department Risks
        risk_res = db.execute(text("""
            SELECT 
                department,
                COUNT(id) as total_alerts,
                SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) as critical_count,
                SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_count
            FROM risk_alerts
            WHERE department IS NOT NULL AND department != ''
            GROUP BY department
            ORDER BY total_alerts DESC;
        """)).mappings().all()
        dept_risks = [
            {
                "department": r["department"],
                "total_alerts": int(r["total_alerts"] or 0),
                "critical_count": int(r["critical_count"] or 0),
                "open_count": int(r["open_count"] or 0),
            }
            for r in risk_res
        ]

        # 6. Customer Fulfillment
        cust_res = db.execute(text("""
            SELECT 
                c.customer_id,
                c.customer_name,
                c.segment,
                COUNT(o.customer_order_id) as total_orders,
                SUM(CASE WHEN o.order_status = 'DELIVERED' THEN 1 ELSE 0 END) as delivered_orders,
                SUM(CASE WHEN o.order_status = 'IN_PRODUCTION' THEN 1 ELSE 0 END) as in_production_orders,
                SUM(CASE WHEN o.order_status IN ('OPEN', 'CONFIRMED') THEN 1 ELSE 0 END) as pending_orders,
                COALESCE(SUM(o.order_qty), 0) as total_units,
                COALESCE(SUM(o.order_qty * o.unit_price_inr), 0) as total_value_inr
            FROM dim_customer c
            LEFT JOIN fact_customer_order o ON c.customer_id = o.customer_id
            GROUP BY c.customer_id, c.customer_name, c.segment
            ORDER BY total_orders DESC;
        """)).mappings().all()
        customers = [
            {
                "customer_id": r["customer_id"],
                "customer_name": r["customer_name"],
                "segment": r["segment"],
                "total_orders": int(r["total_orders"] or 0),
                "delivered_orders": int(r["delivered_orders"] or 0),
                "in_production_orders": int(r["in_production_orders"] or 0),
                "pending_orders": int(r["pending_orders"] or 0),
                "total_units": int(r["total_units"] or 0),
                "total_value_inr": float(r["total_value_inr"] or 0),
            }
            for r in cust_res
        ]

        # 7. KPI Service splits & backlog
        kpi_obj = KPIService.get_kpis(db)
        splits = [
            {"split": s["split"], "count": int(s["count"]), "percentage": float(s["percentage"])}
            for s in kpi_obj.promise_date_accuracy.confirmed_vs_requested_splits
        ]
        backlog = [
            {
                "bucket": b.bucket,
                "order_count": b.order_count,
                "total_quantity": b.total_quantity,
                "total_value_inr": float(b.total_value_inr),
            }
            for b in kpi_obj.backlog_ageing
        ]

        payload = {
            "plant_performance": plants,
            "product_demand": products,
            "carrier_performance": carriers,
            "quality_yield": quality,
            "department_risks": dept_risks,
            "customer_fulfillment": customers,
            "promise_accuracy_splits": splits,
            "backlog_ageing": backlog,
        }
        set_cached(cache_key, payload, ttl_seconds=60)
        return payload

    @classmethod
    def get_customer_orders_progress(cls, db: Session) -> Dict[str, Any]:
        """
        Retrieves authentic customer progress and active order milestone data
        showing customer accounts, committed delivery dates, and progress percentage.
        """
        cache_key = "dashboard:orders_progress"
        cached = get_cached(cache_key)
        if cached:
            return cached

        cust_sql = text("""
            SELECT 
                c.customer_name,
                COUNT(o.customer_order_id) AS total_orders,
                SUM(CASE WHEN o.order_status = 'DELIVERED' THEN 1 ELSE 0 END) AS delivered_count,
                SUM(CASE WHEN o.order_status = 'IN_PRODUCTION' THEN 1 ELSE 0 END) AS in_production_count,
                SUM(CASE WHEN o.order_status = 'PARTIALLY_SHIPPED' THEN 1 ELSE 0 END) AS partially_shipped_count,
                SUM(CASE WHEN o.order_status IN ('OPEN', 'CONFIRMED', 'HUMAN_APPROVAL') THEN 1 ELSE 0 END) AS open_count,
                ROUND(CAST(AVG(
                    CASE 
                        WHEN o.order_status = 'DELIVERED' THEN 100
                        WHEN o.order_status = 'PARTIALLY_SHIPPED' THEN 85
                        WHEN o.order_status = 'IN_PRODUCTION' THEN 60
                        WHEN o.order_status = 'CONFIRMED' THEN 35
                        WHEN o.order_status = 'HUMAN_APPROVAL' THEN 25
                        ELSE 15
                    END
                ) AS numeric), 1) AS avg_progress_pct,
                MIN(COALESCE(o.confirmed_delivery_date, o.requested_delivery_date)) AS next_delivery_date
            FROM dim_customer c
            JOIN fact_customer_order o ON c.customer_id = o.customer_id
            GROUP BY c.customer_id, c.customer_name
            ORDER BY total_orders DESC
        """)
        cust_res = [dict(r._mapping) for r in db.execute(cust_sql).fetchall()]
        customers = [
            {
                "customer_name": r["customer_name"],
                "total_orders": int(r["total_orders"] or 0),
                "delivered_count": int(r["delivered_count"] or 0),
                "in_production_count": int(r["in_production_count"] or 0),
                "partially_shipped_count": int(r["partially_shipped_count"] or 0),
                "open_count": int(r["open_count"] or 0),
                "avg_progress_pct": float(r["avg_progress_pct"] or 0),
                "next_delivery_date": str(r["next_delivery_date"]) if r["next_delivery_date"] else None,
            }
            for r in cust_res
        ]

        orders_sql = text("""
            SELECT 
                o.customer_order_id AS order_id,
                c.customer_name,
                p.product_name,
                o.order_qty,
                o.order_status AS status,
                COALESCE(o.confirmed_delivery_date, o.requested_delivery_date) AS delivery_date,
                CASE 
                    WHEN o.order_status = 'DELIVERED' THEN 100
                    WHEN o.order_status = 'PARTIALLY_SHIPPED' THEN 85
                    WHEN o.order_status = 'IN_PRODUCTION' THEN 60
                    WHEN o.order_status = 'CONFIRMED' THEN 35
                    WHEN o.order_status = 'HUMAN_APPROVAL' THEN 25
                    ELSE 15
                END AS progress_pct,
                CASE 
                    WHEN o.order_status = 'DELIVERED' THEN 'COMPLETED'
                    WHEN COALESCE(o.confirmed_delivery_date, o.requested_delivery_date) < CURRENT_DATE AND o.order_status != 'DELIVERED' THEN 'DELAYED'
                    WHEN o.order_status IN ('IN_PRODUCTION', 'PARTIALLY_SHIPPED') THEN 'ON_TRACK'
                    ELSE 'SCHEDULED'
                END AS health
            FROM fact_customer_order o
            JOIN dim_customer c ON o.customer_id = c.customer_id
            JOIN dim_product p ON o.product_id = p.product_id
            ORDER BY o.order_date DESC
            LIMIT 15
        """)
        orders_res = [dict(r._mapping) for r in db.execute(orders_sql).fetchall()]
        orders = [
            {
                "order_id": r["order_id"],
                "customer_name": r["customer_name"],
                "product_name": r["product_name"],
                "order_qty": int(r["order_qty"] or 0),
                "status": r["status"],
                "delivery_date": str(r["delivery_date"]) if r["delivery_date"] else None,
                "progress_pct": int(r["progress_pct"] or 0),
                "health": r["health"],
            }
            for r in orders_res
        ]

        payload = {
            "customers": customers,
            "orders": orders,
        }
        set_cached(cache_key, payload, ttl_seconds=60)
        return payload

