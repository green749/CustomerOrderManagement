from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy import func, case, select
from sqlalchemy.orm import Session
from ..config import settings
from ..models.business import FactCustomerOrder, FactShipmentMilestone, FactProductionOrder


class DashboardRepository:
    @staticmethod
    def get_summary(db: Session, as_of_date: Optional[date] = None) -> Dict[str, Any]:
        effective_date = as_of_date or settings.effective_reference_date
        horizon_date = effective_date + timedelta(days=3)

        from sqlalchemy import text
        sql = text("""
        WITH order_stats AS (
            SELECT 
                COUNT(*) as total_orders,
                COUNT(CASE WHEN order_status = 'OPEN' THEN 1 END) as open_orders,
                COUNT(CASE WHEN order_status = 'IN_PRODUCTION' THEN 1 END) as in_production_orders,
                COUNT(CASE WHEN order_status = 'PARTIALLY_SHIPPED' THEN 1 END) as partially_shipped_orders,
                COUNT(CASE WHEN order_status = 'DELIVERED' THEN 1 END) as delivered_orders,
                COALESCE(SUM(order_qty * unit_price_inr), 0) as total_val,
                COALESCE(SUM(shipped_qty * unit_price_inr), 0) as shipped_val
            FROM fact_customer_order
        ),
        delayed_milestones AS (
            SELECT DISTINCT customer_order_id
            FROM fact_shipment_milestone
            WHERE shipment_status = 'DELAYED'
        ),
        actual_delayed AS (
            SELECT customer_order_id FROM fact_customer_order
            WHERE order_status != 'DELIVERED' AND confirmed_delivery_date < :eff_date
            UNION
            SELECT customer_order_id FROM delayed_milestones
        ),
        delivered_delayed AS (
            SELECT COUNT(*) as cnt
            FROM fact_customer_order o
            JOIN delayed_milestones m ON o.customer_order_id = m.customer_order_id
            WHERE o.order_status = 'DELIVERED'
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
        fk_stats AS (
            SELECT COUNT(customer_order_id) as has_fk_count
            FROM fact_production_order
            WHERE customer_order_id IS NOT NULL
        )
        SELECT 
            s.*,
            (SELECT COUNT(*) FROM actual_delayed) as actual_delayed_count,
            (SELECT cnt FROM delivered_delayed) as delivered_delayed_count,
            (SELECT COUNT(*) FROM potential_delayed) as potential_delay_count,
            (SELECT COUNT(*) FROM unknown_risk) as unknown_risk_count,
            (SELECT has_fk_count FROM fk_stats) as has_fk_count
        FROM order_stats s
        """)

        row = db.execute(sql, {
            "eff_date": str(effective_date),
            "horizon_date": str(horizon_date),
        }).mappings().first()

        if not row or row["total_orders"] == 0:
            return {
                "total_orders": 0,
                "open_orders": 0,
                "in_production_orders": 0,
                "partially_shipped_orders": 0,
                "delivered_orders": 0,
                "delayed_orders_count": 0,
                "potential_delay_count": 0,
                "unknown_risk_count": 0,
                "total_order_value_inr": Decimal("0.00"),
                "total_shipped_value_inr": Decimal("0.00"),
                "on_time_delivery_rate_pct": 0.0,
                "data_quality_missing_po_count": 0,
            }

        total_orders = row["total_orders"]
        delivered_count = row["delivered_orders"]
        delivered_delayed_count = row["delivered_delayed_count"]
        delivered_on_time_count = max(0, delivered_count - delivered_delayed_count)
        otd_rate = (
            round((delivered_on_time_count / delivered_count) * 100, 2)
            if delivered_count > 0
            else 0.0
        )
        has_fk_count = row["has_fk_count"] or 0
        missing_po_count = max(0, total_orders - has_fk_count)

        return {
            "total_orders": total_orders,
            "open_orders": row["open_orders"],
            "in_production_orders": row["in_production_orders"],
            "partially_shipped_orders": row["partially_shipped_orders"],
            "delivered_orders": delivered_count,
            "delayed_orders_count": row["actual_delayed_count"],
            "potential_delay_count": row["potential_delay_count"],
            "unknown_risk_count": row["unknown_risk_count"],
            "total_order_value_inr": Decimal(row["total_val"] or 0),
            "total_shipped_value_inr": Decimal(row["shipped_val"] or 0),
            "on_time_delivery_rate_pct": otd_rate,
            "data_quality_missing_po_count": missing_po_count,
        }

    @staticmethod
    def get_order_status_distribution(db: Session) -> List[Dict[str, Any]]:
        results = (
            db.query(
                FactCustomerOrder.order_status,
                func.count(FactCustomerOrder.customer_order_id).label("count"),
                func.sum(FactCustomerOrder.order_qty).label("total_qty"),
                func.sum(FactCustomerOrder.order_qty * FactCustomerOrder.unit_price_inr).label("total_value"),
            )
            .group_by(FactCustomerOrder.order_status)
            .all()
        )

        total_count = sum(r[1] for r in results) or 1
        distribution = []
        for r in results:
            distribution.append({
                "status": r[0],
                "count": r[1],
                "percentage": round((r[1] / total_count) * 100, 2),
                "total_qty": int(r[2] or 0),
                "total_value_inr": Decimal(r[3] or 0),
            })
        return distribution

