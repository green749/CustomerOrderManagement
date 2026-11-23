from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.auth import User
from ..services.auth_service import require_role
from ..services.kpi_service import KPIService
from ..schemas.kpis import KPIDashboardResponse, AgentPerformanceKPIResponse

router = APIRouter(prefix="/api/kpis", tags=["KPIs"])


@router.get("", response_model=KPIDashboardResponse)
def get_kpis(
    start_date: Optional[date] = Query(default=None, description="Start date filter"),
    end_date: Optional[date] = Query(default=None, description="End date filter"),
    customer_id: Optional[str] = Query(default=None, description="Customer ID filter (e.g. CUS-001)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["operator", "manager", "admin"])),
):
    """
    Retrieve commercial and operational KPIs calculated via SQL aggregates:
    - Customer OTIF (with Task 1 synthetic data caveat)
    - Order Confirmation Time proxy
    - Production Schedule Adherence
    - Backlog Ageing Buckets (0-7, 8-14, 15-30, 30+ days)
    - Promise-Date Accuracy & Confirmed vs Requested splits
    - Expedite Freight Cost
    """
    return KPIService.get_kpis(
        db=db,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        customer_scope=current_user.customer_scope,
    )


@router.get("/agent-performance", response_model=AgentPerformanceKPIResponse)
def get_agent_performance_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["operator", "manager", "admin", "customer_service"])),
):
    """
    Retrieve autonomous agent governance KPIs:
    - On-time rate for auto-approved vs human-approved
    - Number of agent escalations
    - Average alert-to-resolution time
    """
    return KPIService.get_agent_performance_kpis(db=db)


