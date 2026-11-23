from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.auth import User
from ..services.auth_service import require_role
from ..services.promise_service import PromiseService
from ..schemas.promise import AllocationProposalResponse

router = APIRouter(prefix="/api/allocation", tags=["Allocation"])


@router.get("/proposal", response_model=AllocationProposalResponse)
def get_allocation_proposal(
    product_id: Optional[str] = Query(default=None, description="Optional product ID filter (e.g. SPH-A15-128)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["operator", "manager", "admin"])),
):
    """
    Propose constrained inventory allocation for competing open orders:
    Ranked greedily by priority (HIGH>MEDIUM>LOW), customer service level (OTIF-95),
    and earliest requested delivery date.
    """
    return PromiseService.propose_allocation(db, product_id=product_id)

