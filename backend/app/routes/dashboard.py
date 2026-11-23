from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.dashboard_service import DashboardService
from ..schemas.dashboard import (
    DashboardSummary,
    OrderStatusCount,
    AtRiskSummaryResponse,
    AnalyticsDashboardResponse,
    CustomerOrdersProgressResponse,
)
from ..models.auth import User
from ..services.auth_service import get_current_user, require_role
from ..services.kpi_service import KPIService
from ..schemas.kpis import DeliveryPerformanceResponse, WeeklyTrendsResponse

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve operational KPIs, on-time rates, and order counts."""
    return DashboardService.get_summary(db)


@router.get("/order-status", response_model=List[OrderStatusCount])
def get_order_status_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve distribution of customer orders across statuses."""
    return DashboardService.get_order_status_distribution(db)


@router.get("/analytics", response_model=AnalyticsDashboardResponse)
def get_dashboard_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve multi-dimensional manufacturing operational analytics."""
    return DashboardService.get_analytics(db)


@router.get("/orders-progress", response_model=CustomerOrdersProgressResponse)
def get_customer_orders_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve customer accounts, committed order delivery dates, and real-time completion progress."""
    return DashboardService.get_customer_orders_progress(db)


@router.get("/at-risk", response_model=AtRiskSummaryResponse)
def get_at_risk_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_category: Optional[str] = Query(default=None, description="Filter by ACTUAL_DELAY, POTENTIAL_DELAY, or UNKNOWN_RISK"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List orders categorized as at-risk with transparent rule explanations."""
    return DashboardService.get_at_risk_orders(
        db=db,
        page=page,
        page_size=page_size,
        risk_category=risk_category,
    )


@router.get("/delivery-performance", response_model=DeliveryPerformanceResponse)
def get_delivery_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["operator", "manager", "admin"])),
):
    """Retrieve on-time delivery percentages broken down per customer and per carrier."""
    return KPIService.get_delivery_performance(
        db=db,
        customer_scope=current_user.customer_scope,
    )


@router.get("/trends", response_model=WeeklyTrendsResponse)
def get_weekly_trends(
    weeks: int = Query(default=8, ge=2, le=24, description="Number of weeks to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["operator", "manager", "admin"])),
):
    """Retrieve historical weekly trend of order volume and OTIF performance."""
    return KPIService.get_weekly_trends(
        db=db,
        weeks=weeks,
        customer_scope=current_user.customer_scope,
    )

