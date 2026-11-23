"""postgres_free_tier_indexes_and_summary_view

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-13 17:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Indexes on fact_customer_order
    if 'fact_customer_order' in existing_tables:
        existing_indexes = [idx['name'] for idx in insp.get_indexes('fact_customer_order')]
        
        # Composite: order_status + order_date DESC (for filtered paginated list view)
        if 'idx_fact_customer_order_status_date' not in existing_indexes:
            op.execute("""
                CREATE INDEX IF NOT EXISTS idx_fact_customer_order_status_date
                ON fact_customer_order (order_status, order_date DESC);
            """)

        # Composite: customer_id + order_date DESC (for customer-scoped queries)
        if 'idx_fact_customer_order_customer_date' not in existing_indexes:
            op.execute("""
                CREATE INDEX IF NOT EXISTS idx_fact_customer_order_customer_date
                ON fact_customer_order (customer_id, order_date DESC);
            """)

        # Partial index: confirmed_delivery_date ASC for active unfulfilled orders (overdue surveillance)
        if 'idx_fact_customer_order_active_overdue' not in existing_indexes and dialect == 'postgresql':
            op.execute("""
                CREATE INDEX IF NOT EXISTS idx_fact_customer_order_active_overdue
                ON fact_customer_order (confirmed_delivery_date ASC)
                WHERE order_status IN ('OPEN', 'CONFIRMED', 'IN_PRODUCTION');
            """)

    # 2. Indexes on fact_production_order
    if 'fact_production_order' in existing_tables:
        existing_indexes = [idx['name'] for idx in insp.get_indexes('fact_production_order')]
        if 'idx_fact_production_order_co_status' not in existing_indexes:
            op.execute("""
                CREATE INDEX IF NOT EXISTS idx_fact_production_order_co_status
                ON fact_production_order (customer_order_id, order_status);
            """)

    # 3. Indexes on fact_shipment_milestone
    if 'fact_shipment_milestone' in existing_tables:
        existing_indexes = [idx['name'] for idx in insp.get_indexes('fact_shipment_milestone')]
        if 'idx_fact_shipment_milestone_co_date' not in existing_indexes:
            op.execute("""
                CREATE INDEX IF NOT EXISTS idx_fact_shipment_milestone_co_date
                ON fact_shipment_milestone (customer_order_id, dispatch_date DESC);
            """)

    # 4. Materialized View for Dashboard KPIs (PostgreSQL only)
    if dialect == 'postgresql':
        op.execute("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_order_kpi_summary AS
            SELECT
                COUNT(*) AS total_orders,
                COUNT(*) FILTER (WHERE order_status = 'OPEN') AS open_orders,
                COUNT(*) FILTER (WHERE order_status = 'CONFIRMED') AS confirmed_orders,
                COUNT(*) FILTER (WHERE order_status = 'IN_PRODUCTION') AS in_production_orders,
                COUNT(*) FILTER (WHERE order_status = 'PARTIALLY_SHIPPED') AS partially_shipped_orders,
                COUNT(*) FILTER (WHERE order_status = 'DELIVERED') AS delivered_orders,
                COUNT(*) FILTER (WHERE order_status = 'CANCELLED') AS cancelled_orders,
                COUNT(*) FILTER (WHERE order_status IN ('OPEN', 'CONFIRMED', 'IN_PRODUCTION') AND confirmed_delivery_date < CURRENT_DATE) AS overdue_orders,
                COALESCE(SUM(order_qty), 0) AS total_order_qty,
                COALESCE(SUM(shipped_qty), 0) AS total_shipped_qty,
                CURRENT_TIMESTAMP AS refreshed_at
            FROM fact_customer_order;

            CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_order_kpi_summary ON mv_order_kpi_summary (total_orders);
        """)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_order_kpi_summary CASCADE;")

    op.execute("DROP INDEX IF EXISTS idx_fact_shipment_milestone_co_date;")
    op.execute("DROP INDEX IF EXISTS idx_fact_production_order_co_status;")
    op.execute("DROP INDEX IF EXISTS idx_fact_customer_order_active_overdue;")
    op.execute("DROP INDEX IF EXISTS idx_fact_customer_order_customer_date;")
    op.execute("DROP INDEX IF EXISTS idx_fact_customer_order_status_date;")
