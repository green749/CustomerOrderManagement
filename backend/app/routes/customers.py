import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models.business import DimCustomer, FactCustomerOrder
from ..models.auth import User
from ..services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get("", response_model=List[Dict[str, Any]])
def list_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all customers with real-time aggregate order and volume metrics from PostgreSQL 16."""
    results = (
        db.query(
            DimCustomer.customer_id,
            DimCustomer.customer_name,
            DimCustomer.country,
            DimCustomer.segment,
            func.count(FactCustomerOrder.customer_order_id).label("total_orders"),
            func.coalesce(func.sum(FactCustomerOrder.order_qty), 0).label("total_quantity"),
        )
        .outerjoin(FactCustomerOrder, DimCustomer.customer_id == FactCustomerOrder.customer_id)
        .group_by(DimCustomer.customer_id, DimCustomer.customer_name, DimCustomer.country, DimCustomer.segment)
        .order_by(func.count(FactCustomerOrder.customer_order_id).desc())
        .all()
    )

    customers = []
    for r in results:
        customers.append({
            "customer_id": r.customer_id,
            "customer_name": r.customer_name,
            "country": r.country,
            "segment": r.segment,
            "total_orders": r.total_orders,
            "total_quantity": int(r.total_quantity),
        })
    return customers


@router.get("/{customer_id}", response_model=Dict[str, Any])
def get_customer_detail(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve full customer dossier and operational statistics live from PostgreSQL 16."""
    cust = db.query(DimCustomer).filter(DimCustomer.customer_id == customer_id).first()
    if not cust:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID '{customer_id}' not found.",
        )

    # Status distribution
    status_q = (
        db.query(FactCustomerOrder.order_status, func.count(FactCustomerOrder.customer_order_id))
        .filter(FactCustomerOrder.customer_id == customer_id)
        .group_by(FactCustomerOrder.order_status)
        .all()
    )
    status_counts = {stat or "UNKNOWN": count for stat, count in status_q}

    # Priority distribution
    priority_q = (
        db.query(FactCustomerOrder.priority, func.count(FactCustomerOrder.customer_order_id))
        .filter(FactCustomerOrder.customer_id == customer_id)
        .group_by(FactCustomerOrder.priority)
        .all()
    )
    priority_counts = {prio or "NORMAL": count for prio, count in priority_q}

    # Totals
    total_orders = sum(status_counts.values())
    total_qty = (
        db.query(func.coalesce(func.sum(FactCustomerOrder.order_qty), 0))
        .filter(FactCustomerOrder.customer_id == customer_id)
        .scalar()
    )

    # Distinct products
    products_count = (
        db.query(func.count(func.distinct(FactCustomerOrder.product_id)))
        .filter(FactCustomerOrder.customer_id == customer_id)
        .scalar()
        or 0
    )

    return {
        "customer_id": cust.customer_id,
        "customer_name": cust.customer_name,
        "country": cust.country,
        "segment": cust.segment,
        "total_orders": total_orders,
        "total_quantity": int(total_qty or 0),
        "products_count": products_count,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "database_synced": True,
        "source": "Neon PostgreSQL 16 Star Schema (dim_customer ⋈ fact_customer_order)",
    }
